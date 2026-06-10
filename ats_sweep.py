"""Automated ATS platform sweep via the Google Custom Search JSON API.

Replaces the manual daily routine of clicking through Google searches like
``site:greenhouse.io ("Foreign Policy" OR ...)`` for each ATS platform.
Each platform x query combination becomes one API call; results are mapped
to job dicts compatible with the rest of the pipeline.

Requires two environment variables (free tier: 100 queries/day):
  GOOGLE_PSE_API_KEY  — API key with the Custom Search API enabled
  GOOGLE_PSE_CX       — Programmable Search Engine ID ("search entire web")

Queries and platforms are configured in config.json under "sweep".
"""

import logging
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# Extract the organization slug from common ATS posting URLs
ORG_URL_PATTERNS = [
    re.compile(r'(?:job-boards|boards)\.greenhouse\.io/([^/?#]+)', re.I),
    re.compile(r'greenhouse\.io/embed/job_board\?for=([^&]+)', re.I),
    re.compile(r'jobs\.lever\.co/([^/?#]+)', re.I),
    re.compile(r'jobs\.ashbyhq\.com/([^/?#]+)', re.I),
    re.compile(r'apply\.workable\.com/([^/?#]+)', re.I),
    re.compile(r'jobs\.smartrecruiters\.com/([^/?#]+)', re.I),
    re.compile(r'https?://([^./]+)\.wd\d+\.myworkdayjobs\.com', re.I),
    re.compile(r'https?://(?:careers?[-.])?([^./]+)\.icims\.com', re.I),
    re.compile(r'governmentjobs\.com/careers/([^/?#]+)', re.I),
    re.compile(r'jobs\.jobvite\.com/([^/?#]+)', re.I),
    re.compile(r'https?://([^./]+)\.applytojob\.com', re.I),
    re.compile(r'recruiting\.ultipro\.com/([^/?#]+)', re.I),
    re.compile(r'recruiting\.paylocity\.com/recruiting/jobs/[^/]+/[^/]+/([^/?#]+)', re.I),
]

# Google result titles carry vendor/branding suffixes worth stripping
_TITLE_SUFFIX_RE = re.compile(
    r'\s*[-|–—·]\s*(?:Greenhouse|Lever|Ashby(?:HQ)?|Workable|SmartRecruiters|'
    r'Workday|iCIMS|Jobvite|Paylocity|UKG|UltiPro|Indeed\.com|Job Details|'
    r"(?:[\w&.'’ ]+\s)?Careers?(?:\s+(?:at|page).*)?)\s*$", re.I)
_GH_APPLICATION_RE = re.compile(r'^Job Application for\s+(.*?)(?:\s+at\s+(.+))?$', re.I)


def _prettify_slug(slug: str) -> str:
    name = re.sub(r'[-_]+', ' ', slug).strip()
    # Slugs are usually lowercase; title-case them, but keep ALL-CAPS
    # tenant codes (e.g. Workday tenants) as-is
    return name.title() if not name.isupper() else name


def extract_org_name(url: str) -> Optional[str]:
    for pattern in ORG_URL_PATTERNS:
        m = pattern.search(url)
        if m:
            return _prettify_slug(m.group(1))
    return None


def clean_result_title(title: str) -> str:
    """Strip ATS branding noise from a Google result title."""
    title = (title or '').strip()
    m = _GH_APPLICATION_RE.match(title)
    if m:
        title = m.group(1)
    # Apply suffix stripping twice: titles often look like
    # "Role - Org Careers - Greenhouse"
    for _ in range(2):
        title = _TITLE_SUFFIX_RE.sub('', title).strip()
    return title


class ATSSweeper:
    """Runs configured platform x query searches against the Google API."""

    def __init__(self, api_key: str, cx: str, sweep_config: Dict,
                 timeout: int = 15):
        self.api_key = api_key
        self.cx = cx
        self.timeout = timeout
        self.queries: Dict[str, List[str]] = sweep_config.get('queries', {})
        self.platforms: List[Dict] = sweep_config.get('platforms', [])
        self.date_restrict = sweep_config.get('date_restrict', 'd2')
        self.results_per_query = min(int(sweep_config.get('results_per_query', 10)), 10)
        self.max_api_calls = int(sweep_config.get('max_api_calls', 90))
        self.api_calls_made = 0

    def _build_query(self, site: str, terms: List[str],
                     exclude: List[str] = None) -> str:
        quoted = ' OR '.join(f'"{t}"' for t in terms)
        q = f'site:{site} ({quoted})'
        for term in exclude or []:
            q += f' -"{term}"'
        return q

    def _search(self, q: str) -> List[Dict]:
        """Run one API call; returns raw result items (possibly empty)."""
        if self.api_calls_made >= self.max_api_calls:
            logger.warning("Sweep API budget (%d calls) exhausted — skipping query",
                           self.max_api_calls)
            return []
        self.api_calls_made += 1
        params = {
            'key': self.api_key,
            'cx': self.cx,
            'q': q,
            'num': self.results_per_query,
        }
        if self.date_restrict:
            params['dateRestrict'] = self.date_restrict
        try:
            resp = requests.get(API_ENDPOINT, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                logger.error("Google API quota exceeded (429) — stopping sweep")
                self.api_calls_made = self.max_api_calls
                return []
            resp.raise_for_status()
            return resp.json().get('items', [])
        except requests.RequestException as e:
            logger.error("Sweep search failed: %s", e)
            return []

    def _result_to_job(self, item: Dict, platform: Dict,
                       query_label: str) -> Optional[Dict]:
        url = item.get('link')
        title = clean_result_title(item.get('title', ''))
        if not url or not title:
            return None
        org = extract_org_name(url)
        site_name = f"{org} ({platform['name']})" if org else f"{platform['name']} sweep"
        return {
            'title': title,
            'url': url,
            'description': item.get('snippet'),
            'site_name': site_name,
            'keywords': query_label,
        }

    def sweep(self) -> List[Dict]:
        """Run all platform x query searches. Returns deduped job dicts."""
        jobs: List[Dict] = []
        seen_urls = set()

        for platform in self.platforms:
            site = platform.get('site')
            if not site:
                continue
            for query_label, terms in self.queries.items():
                q = self._build_query(site, terms, platform.get('exclude'))
                items = self._search(q)
                found = 0
                for item in items:
                    job = self._result_to_job(item, platform, query_label)
                    if job and job['url'] not in seen_urls:
                        seen_urls.add(job['url'])
                        jobs.append(job)
                        found += 1
                if found:
                    logger.info("Sweep %s / %s: %d results",
                                platform['name'], query_label, found)
                if self.api_calls_made >= self.max_api_calls:
                    logger.warning("Sweep stopped early after %d API calls",
                                   self.api_calls_made)
                    return jobs

        logger.info("Sweep complete: %d results from %d API calls",
                    len(jobs), self.api_calls_made)
        return jobs
