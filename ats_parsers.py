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


# ── Dispatcher ────────────────────────────────────────────────────────

_PARSERS = {
    'greenhouse': parse_greenhouse,
    'lever': parse_lever,
    'workable': parse_workable,
    'teamtailor': parse_teamtailor,
}


def parse_ats_page(ats: str, soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """Dispatch to the correct ATS parser. Returns [] for unknown ATS."""
    parser = _PARSERS.get(ats)
    if parser is None:
        logger.warning("No parser for ATS type '%s'", ats)
        return []
    return parser(soup, base_url)
