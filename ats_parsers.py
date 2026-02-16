"""
ATS-specific parsers for common applicant tracking systems.

Greenhouse, Lever, and Workable have predictable page structures.
Using dedicated parsers avoids false positives from the generic
auto-detect heuristics and returns richer metadata (location, job
type, etc.) that the generic scraper often misses.
"""

import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def detect_ats(url: str) -> Optional[str]:
    """Return the ATS identifier for *url*, or None if unrecognised."""
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()

    if 'greenhouse.io' in host or 'boards.greenhouse.io' in host:
        return 'greenhouse'
    if 'lever.co' in host or 'jobs.lever.co' in host:
        return 'lever'
    if 'apply.workable.com' in host:
        return 'workable'
    if 'teamtailor.com' in host:
        return 'teamtailor'
    if 'icims.com' in host:
        return 'icims'
    if 'tbe.taleo.net' in host or 'taleo.net' in host:
        return 'taleo'
    if 'myworkdayjobs.com' in host:
        return 'workday'
    if 'workforcenow.adp.com' in host:
        return 'adp'
    if 'applicantpro.com' in host:
        return 'applicantpro'
    return None


# ── Greenhouse ────────────────────────────────────────────────────────

def parse_greenhouse(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Greenhouse job board page.

    Greenhouse boards use a consistent structure:
      <div class="opening">
        <a href="/org/jobs/12345">Title</a>
        <span class="location">City, State</span>
      </div>
    Grouped under <section class="level-0"> department headings.
    """
    jobs = []
    seen = set()

    # Modern Greenhouse board layout
    openings = soup.find_all('div', class_='opening')
    for opening in openings:
        link = opening.find('a', href=True)
        if not link:
            continue
        title = link.get_text(strip=True)
        url = urljoin(base_url, link['href'])
        if url in seen or not title:
            continue
        seen.add(url)

        job = {'title': title, 'url': url}

        loc_elem = opening.find('span', class_='location')
        if loc_elem:
            job['location'] = loc_elem.get_text(strip=True)

        # Department from parent section heading
        section = opening.find_parent('section')
        if section:
            dept_heading = section.find(['h2', 'h3', 'h4'])
            if dept_heading:
                job['department'] = dept_heading.get_text(strip=True)

        jobs.append(job)

    # Alternative: some Greenhouse boards render as a <table>
    if not jobs:
        for row in soup.find_all('tr', class_=re.compile(r'job-post', re.I)):
            link = row.find('a', href=True)
            if not link:
                continue
            title = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not title:
                continue
            seen.add(url)
            job = {'title': title, 'url': url}
            loc_cell = row.find('td', class_=re.compile(r'location', re.I))
            if loc_cell:
                job['location'] = loc_cell.get_text(strip=True)
            jobs.append(job)

    logger.info("Greenhouse parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Lever ─────────────────────────────────────────────────────────────

def parse_lever(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Lever job board page.

    Lever boards use:
      <div class="posting">
        <a class="posting-title" href="https://jobs.lever.co/org/uuid">
          <h5>Title</h5>
          <span class="sort-by-location posting-category small-category-label">City</span>
          <span class="sort-by-commitment posting-category small-category-label">Full-time</span>
        </a>
      </div>
    """
    jobs = []
    seen = set()

    postings = soup.find_all('div', class_='posting')
    for posting in postings:
        link = posting.find('a', class_='posting-title', href=True)
        if not link:
            link = posting.find('a', href=True)
        if not link:
            continue

        # Title is in the <h5> inside the link
        title_elem = link.find('h5')
        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
        url = link['href']

        if url in seen or not title:
            continue
        seen.add(url)

        job = {'title': title, 'url': url}

        # Location and commitment (job type) are in category spans
        categories = posting.find_all('span', class_='posting-category')
        for cat in categories:
            classes = ' '.join(cat.get('class', []))
            text = cat.get_text(strip=True)
            if not text:
                continue
            if 'location' in classes:
                job['location'] = text
            elif 'commitment' in classes:
                job['job_type'] = text
            elif 'team' in classes or 'department' in classes:
                job['department'] = text

        # Department heading (Lever groups postings under department headers)
        dept_parent = posting.find_parent(class_='posting-category-title')
        if not dept_parent:
            # Try the previous sibling header
            prev = posting.find_previous_sibling(class_='posting-category-title')
            if prev:
                job.setdefault('department', prev.get_text(strip=True))

        jobs.append(job)

    logger.info("Lever parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Workable ──────────────────────────────────────────────────────────

def parse_workable(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Workable job board page.

    Workable boards typically render job cards with data attributes or
    list items containing links to individual postings.
    """
    jobs = []
    seen = set()

    # Workable uses <li> or <div> with data-ui="job" or class containing "job"
    job_cards = soup.find_all(
        ['li', 'div', 'a'],
        attrs={'data-ui': re.compile(r'job', re.I)}
    )
    if not job_cards:
        job_cards = soup.find_all(['li', 'div'], class_=re.compile(r'job-listing|job-card', re.I))

    for card in job_cards:
        link = card.find('a', href=True) if card.name != 'a' else card
        if not link:
            continue
        title_elem = card.find(['h3', 'h4', 'span'], class_=re.compile(r'title|name', re.I))
        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
        url = urljoin(base_url, link['href'])

        if url in seen or not title or len(title) < 3:
            continue
        seen.add(url)

        job = {'title': title, 'url': url}
        loc = card.find(['span', 'div'], class_=re.compile(r'location|city', re.I))
        if loc:
            job['location'] = loc.get_text(strip=True)
        jtype = card.find(['span', 'div'], class_=re.compile(r'type|commitment', re.I))
        if jtype:
            job['job_type'] = jtype.get_text(strip=True)

        jobs.append(job)

    # Fallback: look for links containing /j/ (Workable's job path pattern)
    if not jobs:
        for link in soup.find_all('a', href=re.compile(r'/j/', re.I)):
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            seen.add(url)
            jobs.append({'title': text, 'url': url})

    logger.info("Workable parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Teamtailor ────────────────────────────────────────────────────────

def parse_teamtailor(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Teamtailor job board page.

    Teamtailor boards use list items with links to /jobs/<id>-<slug>.
    """
    jobs = []
    seen = set()

    # Teamtailor typically uses <a> elements linking to /jobs/...
    for link in soup.find_all('a', href=re.compile(r'/jobs/\d+', re.I)):
        text = link.get_text(strip=True)
        url = urljoin(base_url, link['href'])
        if url in seen or not text or len(text) < 5:
            continue
        seen.add(url)

        job = {'title': text, 'url': url}
        # Look for location/type in sibling or parent elements
        parent = link.parent
        if parent:
            loc = parent.find(['span', 'div'], class_=re.compile(r'location|city', re.I))
            if loc:
                job['location'] = loc.get_text(strip=True)
            jtype = parent.find(['span', 'div'], class_=re.compile(r'type|status', re.I))
            if jtype:
                job['job_type'] = jtype.get_text(strip=True)
        jobs.append(job)

    logger.info("Teamtailor parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── iCIMS ─────────────────────────────────────────────────────────────

def parse_icims(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse an iCIMS job board page.

    iCIMS boards render job listings as table rows or divs with links
    containing /jobs/<id>/job in the href.  The Brookings instance uses
    a landing page with links to individual postings.
    """
    jobs = []
    seen = set()

    # iCIMS typically renders job links with /jobs/<id>/ paths
    for link in soup.find_all('a', href=re.compile(r'/jobs/\d+', re.I)):
        text = link.get_text(strip=True)
        url = urljoin(base_url, link['href'])
        if url in seen or not text or len(text) < 5:
            continue
        # Skip navigation/filter links
        if text.lower() in ('apply', 'apply now', 'search', 'back'):
            continue
        seen.add(url)

        job = {'title': text, 'url': url}
        parent = link.parent
        if parent:
            loc = parent.find(['span', 'div'], class_=re.compile(r'location|city', re.I))
            if loc:
                job['location'] = loc.get_text(strip=True)
            jtype = parent.find(['span', 'div'], class_=re.compile(r'type|category', re.I))
            if jtype:
                job['job_type'] = jtype.get_text(strip=True)
        jobs.append(job)

    # Fallback: look for iCIMS-style listing containers
    if not jobs:
        for container in soup.find_all(['div', 'li', 'tr'], class_=re.compile(r'iCIMS|job', re.I)):
            link = container.find('a', href=True)
            if not link:
                continue
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            seen.add(url)
            jobs.append({'title': text, 'url': url})

    logger.info("iCIMS parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Taleo ─────────────────────────────────────────────────────────────

def parse_taleo(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Taleo job board page.

    Taleo (Oracle) career sections render job listings in tables or divs.
    The Freedom House instance uses the v2 career site.  Taleo pages are
    often JS-heavy, so this parser works best with Playwright-rendered HTML.
    """
    jobs = []
    seen = set()

    # Taleo v2 uses spans/links with class patterns like "job-link" or
    # requisition rows with data attributes
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True)
        # Taleo job links typically contain requisition IDs or /jobdetail/
        if not text or len(text) < 5:
            continue
        if any(kw in href.lower() for kw in ['requisition', 'jobdetail', 'job/']):
            url = urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)
            job = {'title': text, 'url': url}
            parent = link.parent
            if parent:
                loc = parent.find(['span', 'td'], class_=re.compile(r'location|city', re.I))
                if loc:
                    job['location'] = loc.get_text(strip=True)
            jobs.append(job)

    # Fallback: look for table rows with job data
    if not jobs:
        for row in soup.find_all('tr', class_=re.compile(r'job|requisition|data', re.I)):
            link = row.find('a', href=True)
            if not link:
                continue
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            seen.add(url)
            job = {'title': text, 'url': url}
            cells = row.find_all('td')
            if len(cells) >= 2:
                job['location'] = cells[1].get_text(strip=True)
            jobs.append(job)

    logger.info("Taleo parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Workday ───────────────────────────────────────────────────────────

def parse_workday(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse a Workday job board page.

    Workday career sites (myworkdayjobs.com) are heavily JS-rendered.
    This parser handles the server-rendered HTML that Playwright produces,
    which typically contains job cards with data-automation-id attributes.
    """
    jobs = []
    seen = set()

    # Workday uses data-automation-id="jobTitle" on links
    for link in soup.find_all('a', attrs={'data-automation-id': re.compile(r'jobTitle', re.I)}):
        text = link.get_text(strip=True)
        url = urljoin(base_url, link.get('href', ''))
        if url in seen or not text:
            continue
        seen.add(url)
        job = {'title': text, 'url': url}

        # Location usually in a sibling element
        parent = link.find_parent(['li', 'div', 'section'])
        if parent:
            loc = parent.find(attrs={'data-automation-id': re.compile(r'location', re.I)})
            if loc:
                job['location'] = loc.get_text(strip=True)
            posted = parent.find(attrs={'data-automation-id': re.compile(r'postedOn', re.I)})
            if posted:
                job['posted_date'] = posted.get_text(strip=True)
        jobs.append(job)

    # Fallback: generic link scan for /job/ paths
    if not jobs:
        for link in soup.find_all('a', href=re.compile(r'/job/', re.I)):
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            if text.lower() in ('apply', 'apply now', 'sign in'):
                continue
            seen.add(url)
            jobs.append({'title': text, 'url': url})

    logger.info("Workday parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── ADP ───────────────────────────────────────────────────────────────

def parse_adp(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse an ADP Workforce Now job board page.

    ADP recruitment pages are JS-rendered.  When rendered via Playwright
    the job cards appear as divs/links with job posting data.
    """
    jobs = []
    seen = set()

    # ADP uses links to job detail pages with /mdf/recruitment/ in the path
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        # ADP links often contain requisition or job detail identifiers
        if 'recruitment' in href.lower() or 'requisition' in href.lower():
            url = urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)
            jobs.append({'title': text, 'url': url})

    # Fallback: look for structured job cards
    if not jobs:
        for card in soup.find_all(['div', 'li'], class_=re.compile(r'job|posting|position|requisition', re.I)):
            link = card.find('a', href=True)
            if not link:
                continue
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            seen.add(url)
            job = {'title': text, 'url': url}
            loc = card.find(['span', 'div'], class_=re.compile(r'location', re.I))
            if loc:
                job['location'] = loc.get_text(strip=True)
            jobs.append(job)

    logger.info("ADP parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── ApplicantPro ──────────────────────────────────────────────────────

def parse_applicantpro(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """
    Parse an ApplicantPro job board page.

    ApplicantPro boards render job listings as links to /jobs/<id>/<slug>
    in a list format with location and category metadata.
    """
    jobs = []
    seen = set()

    # ApplicantPro uses /jobs/<number>/ link pattern
    for link in soup.find_all('a', href=re.compile(r'/jobs/\d+', re.I)):
        text = link.get_text(strip=True)
        url = urljoin(base_url, link['href'])
        if url in seen or not text or len(text) < 5:
            continue
        if text.lower() in ('apply', 'apply now', 'view job', 'details'):
            continue
        seen.add(url)

        job = {'title': text, 'url': url}
        parent = link.parent
        if parent:
            loc = parent.find(['span', 'div', 'small'], class_=re.compile(r'location|city|region', re.I))
            if loc:
                job['location'] = loc.get_text(strip=True)
            dept = parent.find(['span', 'div', 'small'], class_=re.compile(r'department|category', re.I))
            if dept:
                job['department'] = dept.get_text(strip=True)
        jobs.append(job)

    # Fallback: look for job listing containers
    if not jobs:
        for container in soup.find_all(['div', 'li', 'tr'], class_=re.compile(r'job|listing|opening|position', re.I)):
            link = container.find('a', href=True)
            if not link:
                continue
            text = link.get_text(strip=True)
            url = urljoin(base_url, link['href'])
            if url in seen or not text or len(text) < 5:
                continue
            seen.add(url)
            jobs.append({'title': text, 'url': url})

    logger.info("ApplicantPro parser found %d jobs on %s", len(jobs), base_url)
    return jobs


# ── Dispatcher ────────────────────────────────────────────────────────

_PARSERS = {
    'greenhouse': parse_greenhouse,
    'lever': parse_lever,
    'workable': parse_workable,
    'teamtailor': parse_teamtailor,
    'icims': parse_icims,
    'taleo': parse_taleo,
    'workday': parse_workday,
    'adp': parse_adp,
    'applicantpro': parse_applicantpro,
}


def parse_ats_page(ats: str, soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """Dispatch to the correct ATS parser. Returns [] for unknown ATS."""
    parser = _PARSERS.get(ats)
    if parser is None:
        logger.warning("No parser for ATS type '%s'", ats)
        return []
    return parser(soup, base_url)
