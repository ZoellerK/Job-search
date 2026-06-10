"""Heuristic filter that weeds out obvious non-job pages.

The generic scraper grabs any link that smells job-adjacent, which pulls in
navigation links ("About us", "Donate Now"), blog posts, program pages, and
careers-index pages. This module classifies a scraped item as a likely job
posting or junk, based on its title and URL. It is intentionally
conservative: when in doubt, the item is kept.
"""

import re
from urllib.parse import urlparse
from typing import Dict, List, Tuple

# Titles that are always navigation/CTA chrome, never a job posting
NAVIGATION_TITLES = {
    'about', 'about us', 'contact', 'contact us', 'donate', 'donate now',
    'donate today', 'give now', 'subscribe', 'sign up', 'log in', 'login',
    'home', 'start', 'news', 'blog', 'events', 'impact', 'our impact',
    'our approach', 'our work', 'our team', 'our people', 'our story',
    'who we are', 'what we do', 'take action', 'get involved',
    'no jobs found', 'download pdf', 'privacy policy', 'terms',
    'terms of service', 'faq', 'faqs', 'newsletter', 'press', 'media',
    'post a job listing', 'post a volunteer opportunity',
    'election protection', 'grants', 'our grants', 'annual report',
}

# Generic call-to-action titles: only a job if the URL points at a
# specific posting (the scraper often picks up "View job" buttons)
GENERIC_CTA_TITLES = {
    'apply', 'apply now', 'apply here', 'view job', 'view jobs',
    'see job', 'learn more', 'read more', 'find out more', 'more info',
    'details', 'view details', 'see full description and apply',
    'complete form', 'careers', 'career', 'jobs', 'job', 'openings',
    'open positions', 'current openings', 'opportunities', 'positions',
    'full-time positions', 'part-time positions', 'view full posting',
    'see all jobs', 'view all jobs', 'work with us', 'join us',
    'join our team',
}

# URL path segments that indicate non-job content (matched as whole segments)
JUNK_PATH_SEGMENTS = {
    'donate', 'donation', 'donations', 'give', 'giving',
    'about', 'about-us', 'contact', 'contact-us',
    'news', 'blog', 'press', 'media', 'events', 'event', 'stories', 'story',
    'reports', 'report', 'programs', 'program', 'projects', 'project',
    'publications', 'research-reports', 'newsletter', 'subscribe',
    'privacy', 'terms', 'faq', 'faqs', 'sitemap', 'resources',
    'who-we-are', 'what-we-do', 'our-approach', 'our-work', 'our-team',
    'take-action', 'get-involved', 'impact', 'grants', 'grantees',
    'login', 'signin', 'sign-up', 'checkout',
}

# Hosts that never serve this user's job postings (donation/newsletter
# platforms, social media, ATS vendor marketing pages). Matched exactly,
# so org job boards on subdomains (acme.teamtailor.com) are unaffected.
JUNK_HOSTS = {
    'mailchi.mp', 'list-manage.com', 'classy.org', 'givebutter.com',
    'paypal.com', 'eventbrite.com', 'facebook.com', 'twitter.com', 'x.com',
    'instagram.com', 'youtube.com', 'linkedin.com',
    'teamtailor.com', 'greenhouse.io', 'lever.co',
}

# URL patterns that strongly indicate a specific job posting
STRONG_JOB_URL_PATTERNS = [
    re.compile(r'/jobs?/\d+'),
    re.compile(r'/jobs?/[a-z0-9]+(?:-[a-z0-9]+)+', re.I),
    re.compile(r'/careers?/[a-z0-9]+(?:-[a-z0-9]+)+/?$', re.I),
    re.compile(r'/o/[a-z0-9-]+', re.I),                      # Recruitee-style
    re.compile(r'greenhouse\.io/[^/]+/jobs/\d+', re.I),
    re.compile(r'lever\.co/[^/]+/[0-9a-f-]{36}', re.I),
    re.compile(r'[?&]gh_jid=\d+'),
    re.compile(r'workable\.com/.+/j/', re.I),
    re.compile(r'icims\.com/jobs/\d+', re.I),
    re.compile(r'/postings?/[^/]+', re.I),
    re.compile(r'/position/[a-z0-9]+(?:-[a-z0-9]+)+', re.I),
    re.compile(r'bamboohr\.com/careers/\d+', re.I),
    re.compile(r'breezy\.hr/p/[a-z0-9]+', re.I),
    re.compile(r'[?&]ShowJob=\d+', re.I),
]

# Word-boundary role indicators — a title containing one of these is kept
# even when the URL path looks junky (e.g. a posting filed under /news/)
ROLE_WORDS_RE = re.compile(
    r'\b(director|manager|officer|coordinator|analyst|associate|specialist|'
    r'engineer|developer|designer|researcher|consultant|strategist|counsel|'
    r'advisor|adviser|fellow|intern|internship|assistant|administrator|'
    r'accountant|attorney|lead|head of|chief|vice president|president|'
    r'executive|vp)\b', re.I)

MAX_TITLE_LENGTH = 100

# Job-board cards often run the whole card text together:
# "Campaigns ManagerHip Hop CaucusRemoteUSD $70,000...". The real title
# ends at the first jammed-together word boundary.
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z\)'%])(?=[A-Z])")


def salvage_title(title: str) -> str:
    """Recover the leading job title from run-together card text.
    Returns '' when no usable title can be extracted."""
    for m in _CAMEL_BOUNDARY_RE.finditer(title):
        if m.start() >= 10:
            candidate = title[:m.start()].strip()
            return candidate if len(candidate) <= MAX_TITLE_LENGTH else ''
    return ''


def _normalize_title(title: str) -> str:
    t = (title or '').lower().strip()
    t = re.sub(r'[^\w\s-]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _is_strong_job_url(url: str) -> bool:
    return any(p.search(url) for p in STRONG_JOB_URL_PATTERNS)


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith('www.') else host


def classify_job(job: Dict) -> Tuple[bool, str]:
    """Classify a scraped item. Returns (is_likely_job, reason).

    reason is '' when the item is kept, otherwise a short explanation of
    why it was rejected (useful for logging/debugging).
    """
    title = (job.get('title') or '').strip()
    url = (job.get('url') or '').strip()

    if not title or not url:
        return False, 'missing title or URL'

    if len(title) > MAX_TITLE_LENGTH:
        title = salvage_title(title)
        if not title:
            return False, 'title too long (page text, not a job title)'

    normalized = _normalize_title(title)

    if normalized in NAVIGATION_TITLES:
        return False, f'navigation title: {title!r}'

    if normalized in GENERIC_CTA_TITLES:
        # The scraper grabbed button text; keep only if the URL itself
        # identifies a specific posting
        path_text = re.sub(r'[-_/+.]', ' ', urlparse(url).path)
        if _is_strong_job_url(url) or ROLE_WORDS_RE.search(path_text):
            return True, ''
        return False, f'generic CTA title without job URL: {title!r}'

    host = _host(url)
    if host in JUNK_HOSTS:
        return False, f'junk domain: {host}'

    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if not path:
        return False, 'links to site homepage, not a posting'

    segments = {s.lower() for s in path.split('/')}
    if segments & JUNK_PATH_SEGMENTS:
        if _is_strong_job_url(url) or ROLE_WORDS_RE.search(title):
            return True, ''
        junk = ', '.join(sorted(segments & JUNK_PATH_SEGMENTS))
        return False, f'non-job URL path ({junk})'

    return True, ''


def is_likely_job(job: Dict) -> bool:
    """Convenience wrapper: True when the item looks like a real posting."""
    return classify_job(job)[0]


def filter_jobs(jobs: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Split jobs into (kept, rejected). Rejected items get a
    'filter_reason' key explaining the decision."""
    kept, rejected = [], []
    for job in jobs:
        ok, reason = classify_job(job)
        if ok:
            title = (job.get('title') or '').strip()
            if len(title) > MAX_TITLE_LENGTH:
                job = dict(job)
                job['title'] = salvage_title(title)
            kept.append(job)
        else:
            job = dict(job)
            job['filter_reason'] = reason
            rejected.append(job)
    return kept, rejected
