import logging
import threading
import time
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Playwright is optional — only used as a JS-rendering fallback
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class DomainThrottler:
    """Per-domain rate limiter so we don't hammer any single host."""

    def __init__(self, default_delay: float = 1.0):
        self.default_delay = default_delay
        self._lock = threading.Lock()
        self._last_request: Dict[str, float] = {}
        # Domains that asked us to slow down (429)
        self._backoff: Dict[str, float] = defaultdict(lambda: 0.0)

    def wait(self, domain: str):
        with self._lock:
            delay = max(self.default_delay, self._backoff[domain])
            last = self._last_request.get(domain, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_request[domain] = time.monotonic()

    def record_429(self, domain: str):
        """Double the back-off for this domain (capped at 60 s)."""
        with self._lock:
            current = self._backoff[domain] or self.default_delay
            self._backoff[domain] = min(current * 2, 60.0)
            logger.warning("429 from %s — backing off to %.1fs", domain, self._backoff[domain])


class JobScraper:
    """Scrapes job postings from websites"""

    # Titles that are clearly navigation / boilerplate, not job postings
    _NON_JOB_TITLES = frozenset({
        # Navigation / site sections
        'about', 'about us', 'our approach', 'our mission', 'our impact',
        'our people', 'impact', 'take action', 'home', 'careers', 'jobs',
        'open positions', 'current openings', 'our people and careers',
        'work with us', 'our team', 'our work', 'what we do', 'who we are',
        'get involved', 'support us', 'news', 'events', 'resources',
        'privacy policy', 'terms of service',
        # Donation / engagement actions
        'donate', 'donate now', 'subscribe', 'sign up', 'contact',
        'contact us', 'learn more', 'find out more', 'download pdf',
        'read more', 'complete form', 'submit',
        # Meta / system boilerplate
        'hiring software', 'start', 'partners',
    })

    _NON_JOB_PREFIXES = (
        'no jobs found',
        'applicant tracking system',
        'jobs powered by',
        'employer resources',
        'career advice',
        'nonprofit salary',
        'submit position',
        'post a job',
        'post a volunteer',
    )

    # Cookie / consent boilerplate markers
    _BOILERPLATE_MARKERS = (
        'technical storage or access',
        'this website uses cookies',
        'we use cookies',
        'cookie consent',
        'cookie policy',
        'manage consent',
        'accept all cookies',
        'by clicking "accept"',
        'by continuing to browse',
    )

    def __init__(self, user_agent: str = None, timeout: int = 30,
                 retry_attempts: int = 3, domain_delay: float = 1.0):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self._local = threading.local()
        self.throttler = DomainThrottler(default_delay=domain_delay)

    def _get_session(self) -> requests.Session:
        """Get a thread-local requests session (requests.Session is not thread-safe)"""
        if not hasattr(self._local, 'session'):
            self._local.session = requests.Session()
            self._local.session.headers.update({'User-Agent': self.user_agent})
        return self._local.session

    def fetch_page(self, url: str, use_js: bool = False) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a web page with retries.

        Returns (soup, http_status) when called internally, but public API
        still returns just soup for backward compat.
        """
        result = self._fetch_page_internal(url, use_js=use_js)
        return result[0] if result else None

    def _fetch_page_internal(self, url: str, use_js: bool = False):
        """Returns (soup, http_status) or None on total failure."""
        domain = urlparse(url).netloc
        session = self._get_session()
        last_status = None

        for attempt in range(self.retry_attempts):
            self.throttler.wait(domain)
            try:
                response = session.get(url, timeout=self.timeout)
                last_status = response.status_code

                if response.status_code == 429:
                    self.throttler.record_429(domain)
                    logger.warning("Attempt %d: 429 Too Many Requests for %s", attempt + 1, url)
                    if attempt < self.retry_attempts - 1:
                        retry_after = int(response.headers.get('Retry-After', 2 ** (attempt + 1)))
                        time.sleep(min(retry_after, 30))
                    continue

                if response.status_code == 403:
                    logger.warning("403 Forbidden for %s — may need JS rendering", url)
                    if HAS_PLAYWRIGHT and not use_js:
                        return self._fetch_with_playwright(url)
                    return (None, 403)

                if response.status_code == 404:
                    logger.warning("404 Not Found for %s", url)
                    return (None, 404)

                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'lxml')

                # Heuristic: if page looks empty, try Playwright
                if not use_js and self._page_looks_empty(soup) and HAS_PLAYWRIGHT:
                    logger.info("Page %s looks JS-rendered — trying Playwright", url)
                    pw_result = self._fetch_with_playwright(url)
                    if pw_result and pw_result[0]:
                        return pw_result

                return (soup, response.status_code)

            except requests.RequestException as e:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error("Failed to fetch %s after %d attempts", url, self.retry_attempts)
                    return (None, last_status)

        return (None, last_status)

    @staticmethod
    def _page_looks_empty(soup: BeautifulSoup) -> bool:
        """Detect pages that are likely JS-rendered shells with no real content."""
        text = soup.get_text(strip=True)
        # Very short body text likely means content is loaded via JS
        if len(text) < 200:
            return True
        # Common SPA shells
        if soup.find(id='__next') or soup.find(id='root') or soup.find(id='app'):
            if not soup.find_all(['article', 'li', 'tr'], limit=3):
                return True
        return False

    def _fetch_with_playwright(self, url: str):
        """Fetch page using Playwright (headless Chromium). Returns (soup, status) or (None, None)."""
        if not HAS_PLAYWRIGHT:
            return (None, None)
        logger.info("Fetching %s with Playwright", url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.user_agent)
                resp = page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
                status = resp.status if resp else None
                content = page.content()
                browser.close()
            return (BeautifulSoup(content, 'lxml'), status)
        except Exception as e:
            logger.error("Playwright failed for %s: %s", url, e)
            return (None, None)

    # ── Quality filters ─────────────────────────────────────────────

    @staticmethod
    def _is_likely_job_title(title: str) -> bool:
        """Return False for text that is clearly not a job title."""
        if not title or not title.strip():
            return False

        clean = title.strip()
        lower = clean.lower()

        # Reject known non-job patterns (exact match)
        if lower in JobScraper._NON_JOB_TITLES:
            return False

        # Reject known prefixes
        if lower.startswith(JobScraper._NON_JOB_PREFIXES):
            return False

        # Reject email addresses
        if '@' in clean and '.' in clean.split('@')[-1]:
            return False

        # Reject absurdly long titles (likely scraped body text)
        if len(clean) > 150:
            return False

        return True

    @staticmethod
    def _sanitize_description(text: str) -> Optional[str]:
        """Strip cookie/consent boilerplate from description text."""
        if not text:
            return text

        # Split into paragraphs and drop any that contain boilerplate
        paragraphs = re.split(r'\n{2,}', text)
        clean = []
        for para in paragraphs:
            lower = para.lower()
            if any(marker in lower for marker in JobScraper._BOILERPLATE_MARKERS):
                continue
            clean.append(para)

        result = '\n\n'.join(clean).strip()
        return result if len(result) > 20 else None

    # ── Public scraping methods (unchanged API) ───────────────────────

    def auto_detect_jobs(self, url: str) -> List[Dict]:
        """Attempt to automatically detect job listings on a page"""
        soup = self.fetch_page(url)
        if not soup:
            return []

        jobs = []
        seen_urls = set()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        job_patterns = [
            {'container': 'div', 'class_patterns': ['job', 'position', 'opening', 'listing', 'career', 'opportunity', 'vacancy', 'role', 'post']},
            {'container': 'li', 'class_patterns': ['job', 'position', 'opening', 'listing', 'opportunity', 'role']},
            {'container': 'article', 'class_patterns': ['job', 'position', 'opening', 'opportunity', 'post']},
            {'container': 'tr', 'class_patterns': ['job', 'position', 'opening', 'row']},
            {'container': 'section', 'class_patterns': ['job', 'position', 'listing']},
            {'container': 'a', 'class_patterns': ['job-link', 'position-link', 'job-card', 'opportunity']},
        ]

        for pattern in job_patterns:
            containers = soup.find_all(pattern['container'])
            for container in containers:
                classes = container.get('class', [])
                class_tokens = {token for cls in classes for token in re.split(r'[-_]', cls.lower())}
                if any(keyword in class_tokens for keyword in pattern['class_patterns']):
                    job = self._extract_job_from_element(container, base_url)
                    if job and job.get('title') and job.get('url') not in seen_urls:
                        jobs.append(job)
                        seen_urls.add(job.get('url'))

        if not jobs:
            jobs = self._extract_jobs_from_links(soup, base_url)

        # Filter out non-job entries (nav links, donation pages, etc.)
        jobs = [j for j in jobs if self._is_likely_job_title(j.get('title', ''))]

        return jobs

    def _extract_job_from_element(self, element, base_url: str) -> Dict:
        job = {}
        generic_texts = [
            'apply now', 'apply', 'view job', 'view position', 'learn more',
            'read more', 'details', 'more info', 'find out more', 'download pdf',
            'see full description and apply', 'complete form',
            'view current openings', 'explore our job openings',
            'submit position here',
        ]

        title_tags = ['h1', 'h2', 'h3', 'h4', 'a']
        for tag in title_tags:
            title_elem = element.find(tag)
            if title_elem:
                job['title'] = title_elem.get_text(strip=True)
                break

        link = element.find('a', href=True)
        if link:
            href = link['href']
            job['url'] = urljoin(base_url, href)
        elif job.get('title'):
            job['url'] = base_url

        if job.get('title') and job.get('url'):
            if job['title'].lower() in generic_texts:
                url_title = self._extract_title_from_url(job['url'])
                if url_title:
                    job['title'] = url_title

        location_keywords = ['location', 'city', 'office', 'remote']
        for keyword in location_keywords:
            loc_elem = element.find(class_=re.compile(keyword, re.I))
            if loc_elem:
                job['location'] = loc_elem.get_text(strip=True)
                break

        desc_elem = element.find('p') or element.find('div', class_=re.compile('desc', re.I))
        if desc_elem:
            job['description'] = desc_elem.get_text(strip=True)[:2000]

        return job

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            segments = [s for s in path.split('/') if s]
            if not segments:
                return None

            skip_patterns = ['jobs', 'job', 'careers', 'career', 'apply', 'opening', 'openings', 'position',
                           'positions', 'o', 'postings', 'posting', 'details', 'detail', 'opportunitydetail',
                           'single-offer-career', 'careers-list', 'job-board', 'employment', 'work']

            not_title_patterns = [
                r'^\d+$',
                r'^[a-f0-9]{8,}$',
                r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
                r'^gh_jid=',
                r'^jobId=',
                r'^\w{2,3}\d+',
                r'^(scl|fi)$',
            ]

            title_segment = None
            for segment in reversed(segments):
                if any(re.match(pattern, segment, re.I) for pattern in not_title_patterns):
                    continue
                if segment.lower() in skip_patterns:
                    continue
                if len(segment) < 3:
                    continue
                if '-' not in segment and '_' not in segment and len(segment.split()) == 1:
                    common_company_indicators = ['leadingeducators', 'stradaeducation', 'rethinkpriorities',
                                                'thehumaneleague', 'civicnation', 'catalyst']
                    if segment.lower() in common_company_indicators or len(segment) < 10:
                        continue
                title_segment = segment
                break

            if not title_segment:
                return None

            title = re.sub(r'[-_+]', ' ', title_segment)
            title = re.sub(r'\.(pdf|doc|docx)$', '', title, flags=re.I)
            title = re.sub(r'\s+\d+$', '', title)
            title = re.sub(r'\?.*$', '', title)
            title = re.sub(r'^(job[\s-]*(announcement|posting|opening|description)[\s-]*)', '', title, flags=re.I)
            title = title.title()
            title = re.sub(r'\s+', ' ', title).strip()

            if len(title) > 10 or len(title.split()) > 1:
                return title
            return None
        except Exception:
            return None

    def _extract_jobs_from_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        jobs = []
        seen_urls = set()
        job_keywords = ['job', 'position', 'career', 'opening', 'vacancy', 'role', 'opportunity', 'apply', 'hiring', 'employment']
        exclude_keywords = ['home', 'about', 'contact', 'privacy', 'terms', 'login', 'sign', 'search', 'filter', 'sort', 'category', 'donate', 'subscribe', 'newsletter']
        generic_texts = [
            'apply now', 'apply', 'view job', 'view position', 'learn more',
            'read more', 'details', 'more info', 'find out more', 'download pdf',
            'see full description and apply', 'complete form',
            'view current openings', 'explore our job openings',
            'submit position here',
        ]

        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            full_url = urljoin(base_url, href)

            if full_url in seen_urls:
                continue
            if any(exclude in href.lower() or exclude in text.lower() for exclude in exclude_keywords):
                continue

            if any(keyword in href.lower() or keyword in text.lower() for keyword in job_keywords):
                if text and 5 < len(text) < 200:
                    parent = link.parent
                    description = None
                    location = None

                    if parent:
                        desc_elem = parent.find('p') or parent.find('div', class_=re.compile('desc|summary', re.I))
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)[:2000]
                        loc_elem = parent.find(class_=re.compile('location|city|region', re.I))
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)

                    title = text
                    if text.lower() in generic_texts:
                        url_title = self._extract_title_from_url(full_url)
                        if url_title:
                            title = url_title
                        else:
                            continue  # skip if generic text and no URL title

                    jobs.append({
                        'title': title,
                        'url': full_url,
                        'description': description,
                        'location': location
                    })
                    seen_urls.add(full_url)

        return jobs

    def scrape_with_config(self, url: str, parser_config: Dict) -> List[Dict]:
        soup = self.fetch_page(url)
        if not soup:
            return []

        jobs = []
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        if 'url_pattern' in parser_config:
            return self._scrape_by_url_pattern(soup, base_url, parser_config)

        container_config = parser_config.get('job_container', {})
        containers = soup.find_all(
            container_config.get('tag', 'div'),
            class_=container_config.get('class')
        )

        for container in containers:
            job = {'url': url}
            for field, field_config in parser_config.items():
                if field == 'job_container':
                    continue
                element = container.find(
                    field_config.get('tag'),
                    class_=field_config.get('class')
                )
                if element:
                    if field == 'url' and 'attr' in field_config:
                        job[field] = urljoin(base_url, element.get(field_config['attr'], ''))
                    else:
                        job[field] = element.get_text(strip=True)

            if job.get('title'):
                jobs.append(job)

        return jobs

    def _scrape_by_url_pattern(self, soup: BeautifulSoup, base_url: str, config: Dict) -> List[Dict]:
        jobs = []
        seen_urls = set()
        url_pattern = config.get('url_pattern', '')
        exclude_patterns = config.get('exclude_patterns', [])

        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            if url_pattern not in href:
                continue
            if any(exclude in href for exclude in exclude_patterns):
                continue

            text = link.get_text(strip=True)
            if text and 5 < len(text) < 200:
                parent = link.parent
                description = None
                location = None

                if parent:
                    desc_elem = parent.find('p') or parent.find('div', class_=re.compile('desc|summary|snippet', re.I))
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)[:2000]
                    loc_elem = parent.find(class_=re.compile('location|city|region|where', re.I))
                    if loc_elem:
                        location = loc_elem.get_text(strip=True)

                jobs.append({
                    'title': text,
                    'url': full_url,
                    'description': description,
                    'location': location
                })
                seen_urls.add(full_url)

        return jobs

    def scrape_job_details(self, job_url: str) -> Dict:
        soup = self.fetch_page(job_url)
        if not soup:
            return {}

        details = {}

        # Description
        description = None
        desc_patterns = [
            {'class': re.compile(r'(job-)?description', re.I)},
            {'id': re.compile(r'(job-)?description', re.I)},
            {'class': re.compile(r'job-details?', re.I)},
            {'class': re.compile(r'job-content', re.I)},
            {'class': re.compile(r'posting-content', re.I)},
            {'class': re.compile(r'position-description', re.I)},
        ]

        for pattern in desc_patterns:
            desc_elem = soup.find(['div', 'section', 'article'], **pattern)
            if desc_elem:
                description = desc_elem.get_text(separator='\n', strip=True)
                break

        if not description:
            main_content = soup.find('main') or soup.find(id='main') or soup.find(class_=re.compile('main', re.I))
            if main_content:
                text_blocks = main_content.find_all(['div', 'section', 'article'])
                if text_blocks:
                    largest = max(text_blocks, key=lambda x: len(x.get_text(strip=True)))
                    if len(largest.get_text(strip=True)) > 100:
                        description = largest.get_text(separator='\n', strip=True)

        if not description:
            paragraphs = soup.find_all('p')
            if len(paragraphs) > 3:
                description = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)

        if description:
            description = self._sanitize_description(description)
        if description:
            details['description'] = description[:5000]

        # Location
        location_patterns = [
            {'class': re.compile(r'location', re.I)},
            {'id': re.compile(r'location', re.I)},
            {'class': re.compile(r'job-location', re.I)},
            {'class': re.compile(r'(office|city|region)', re.I)},
        ]
        for pattern in location_patterns:
            loc_elem = soup.find(['span', 'div', 'p', 'li'], **pattern)
            if loc_elem:
                location_text = loc_elem.get_text(strip=True)
                if location_text and 5 < len(location_text) < 100:
                    details['location'] = location_text
                    break

        # Salary
        salary_patterns = [
            {'class': re.compile(r'salary|compensation|pay', re.I)},
            {'id': re.compile(r'salary|compensation', re.I)},
        ]
        for pattern in salary_patterns:
            salary_elem = soup.find(['span', 'div', 'p'], **pattern)
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                if salary_text and 5 < len(salary_text) < 200:
                    details['salary'] = salary_text
                    break

        # Job type
        job_type_patterns = [
            {'class': re.compile(r'job-?type|employment-?type', re.I)},
            {'id': re.compile(r'job-?type', re.I)},
        ]
        for pattern in job_type_patterns:
            type_elem = soup.find(['span', 'div', 'p', 'li'], **pattern)
            if type_elem:
                type_text = type_elem.get_text(strip=True)
                if type_text and len(type_text) < 50:
                    details['job_type'] = type_text
                    break

        # Posted date
        date_patterns = [
            {'class': re.compile(r'posted|date|publish', re.I)},
            {'id': re.compile(r'posted|date', re.I)},
        ]
        for pattern in date_patterns:
            date_elem = soup.find(['span', 'div', 'p', 'time'], **pattern)
            if date_elem:
                if date_elem.name == 'time' and date_elem.get('datetime'):
                    details['posted_date'] = date_elem['datetime']
                    break
                else:
                    date_text = date_elem.get_text(strip=True)
                    if date_text and 5 < len(date_text) < 100:
                        details['posted_date'] = date_text
                        break

        return details

    def enrich_jobs_with_details(self, jobs: List[Dict], max_jobs: int = 50) -> List[Dict]:
        enriched_jobs = []

        for i, job in enumerate(jobs[:max_jobs]):
            if not job.get('url'):
                enriched_jobs.append(job)
                continue
            if job.get('description'):
                enriched_jobs.append(job)
                continue

            logger.info("Enriching job %d/%d: %s", i + 1, min(len(jobs), max_jobs), job.get('title', 'Unknown'))

            details = self.scrape_job_details(job['url'])
            enriched_job = {**job, **details}
            enriched_jobs.append(enriched_job)

            if i < len(jobs) - 1:
                time.sleep(0.5)

        return enriched_jobs

    def test_selectors(self, url: str) -> Dict:
        soup = self.fetch_page(url)
        if not soup:
            return {'error': 'Failed to fetch page'}

        info = {
            'title': soup.title.string if soup.title else 'No title',
            'common_classes': [],
            'common_tags': {},
            'links_count': len(soup.find_all('a')),
        }

        all_classes = []
        for elem in soup.find_all(class_=True):
            all_classes.extend(elem.get('class', []))

        class_counts = {}
        for cls in all_classes:
            class_counts[cls] = class_counts.get(cls, 0) + 1

        info['common_classes'] = sorted(
            class_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        for tag in ['div', 'article', 'section', 'li', 'tr']:
            info['common_tags'][tag] = len(soup.find_all(tag))

        return info
