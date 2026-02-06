import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re
from urllib.parse import urljoin, urlparse


class JobScraper:
    """Scrapes job postings from websites"""

    def __init__(self, user_agent: str = None, timeout: int = 30, retry_attempts: int = 3):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page with retries"""
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'lxml')
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"Failed to fetch {url} after {self.retry_attempts} attempts")
                    return None

    def auto_detect_jobs(self, url: str) -> List[Dict]:
        """
        Attempt to automatically detect job listings on a page
        Uses common patterns found on career pages
        """
        soup = self.fetch_page(url)
        if not soup:
            return []

        jobs = []
        seen_urls = set()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Enhanced patterns for job listings - more comprehensive
        job_patterns = [
            {'container': 'div', 'class_patterns': ['job', 'position', 'opening', 'listing', 'career', 'opportunity', 'vacancy', 'role', 'post']},
            {'container': 'li', 'class_patterns': ['job', 'position', 'opening', 'listing', 'opportunity', 'role']},
            {'container': 'article', 'class_patterns': ['job', 'position', 'opening', 'opportunity', 'post']},
            {'container': 'tr', 'class_patterns': ['job', 'position', 'opening', 'row']},
            {'container': 'section', 'class_patterns': ['job', 'position', 'listing']},
            {'container': 'a', 'class_patterns': ['job-link', 'position-link', 'job-card', 'opportunity']},
        ]

        # Try each pattern
        for pattern in job_patterns:
            containers = soup.find_all(pattern['container'])
            for container in containers:
                # Check if any class token matches job-related keywords
                classes = container.get('class', [])
                class_tokens = {token for cls in classes for token in re.split(r'[-_]', cls.lower())}
                if any(keyword in class_tokens for keyword in pattern['class_patterns']):
                    job = self._extract_job_from_element(container, base_url)
                    if job and job.get('title') and job.get('url') not in seen_urls:
                        jobs.append(job)
                        seen_urls.add(job.get('url'))

        # If no jobs found with class patterns, look for common link patterns
        if not jobs:
            jobs = self._extract_jobs_from_links(soup, base_url)

        return jobs

    def _extract_job_from_element(self, element, base_url: str) -> Dict:
        """Extract job information from a DOM element"""
        job = {}

        # Generic link texts that should be replaced with URL-extracted titles
        generic_texts = ['apply now', 'apply', 'view job', 'learn more', 'read more', 'details', 'more info']

        # Try to find title
        title_tags = ['h1', 'h2', 'h3', 'h4', 'a']
        for tag in title_tags:
            title_elem = element.find(tag)
            if title_elem:
                job['title'] = title_elem.get_text(strip=True)
                break

        # Try to find URL
        link = element.find('a', href=True)
        if link:
            href = link['href']
            job['url'] = urljoin(base_url, href)
        elif job.get('title'):
            # If we have title but no link, use the page URL
            job['url'] = base_url

        # If title is generic (like "Apply Now"), try to extract from URL
        if job.get('title') and job.get('url'):
            if job['title'].lower() in generic_texts:
                url_title = self._extract_title_from_url(job['url'])
                if url_title:
                    job['title'] = url_title

        # Try to find location
        location_keywords = ['location', 'city', 'office', 'remote']
        for keyword in location_keywords:
            loc_elem = element.find(class_=re.compile(keyword, re.I))
            if loc_elem:
                job['location'] = loc_elem.get_text(strip=True)
                break

        # Get description (if available)
        desc_elem = element.find('p') or element.find('div', class_=re.compile('desc', re.I))
        if desc_elem:
            job['description'] = desc_elem.get_text(strip=True)[:2000]  # Increased limit for more detail

        return job

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """
        Extract a meaningful job title from a URL slug.
        Handles common URL patterns from job boards and ATSes.

        Examples:
            /program-partnerships-manager-connected/ -> Program Partnerships Manager Connected
            /associate-director-of-program-implementation -> Associate Director Of Program Implementation
            /Grants-Project-Manager -> Grants Project Manager
            /jobs/5073319008 -> None (just an ID)
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')

            # Also check query parameters for job title info
            query_params = {}
            if parsed.query:
                from urllib.parse import parse_qs
                query_params = parse_qs(parsed.query)

            # Split path into segments
            segments = [s for s in path.split('/') if s]

            if not segments:
                return None

            # Common ATS patterns to skip
            skip_patterns = ['jobs', 'job', 'careers', 'career', 'apply', 'opening', 'openings', 'position',
                           'positions', 'o', 'postings', 'posting', 'details', 'detail', 'opportunitydetail',
                           'single-offer-career', 'careers-list', 'job-board', 'employment', 'work']

            # Patterns that indicate a segment is NOT a job title
            # Pure numbers, UUIDs, short hashes
            not_title_patterns = [
                r'^\d+$',  # Pure numbers
                r'^[a-f0-9]{8,}$',  # Hex strings (8+ chars)
                r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',  # UUIDs
                r'^gh_jid=',  # Greenhouse job ID param
                r'^jobId=',  # Generic job ID param
                r'^\w{2,3}\d+',  # Code + numbers like F7, p49, B617
                r'^(scl|fi)$',  # Dropbox segments
            ]

            # Work backwards through segments to find title
            title_segment = None
            for segment in reversed(segments):
                # Skip if matches non-title patterns
                if any(re.match(pattern, segment, re.I) for pattern in not_title_patterns):
                    continue

                # Skip common ATS path segments
                if segment.lower() in skip_patterns:
                    continue

                # Skip very short segments (likely not titles)
                if len(segment) < 3:
                    continue

                # Skip if segment looks like a domain or company name
                # (single word, no separators, all lowercase or starts with capital)
                if '-' not in segment and '_' not in segment and len(segment.split()) == 1:
                    # Could be company name or generic term, be cautious
                    # Only skip if it's very short or in a blocklist
                    common_company_indicators = ['leadingeducators', 'stradaeducation', 'rethinkpriorities',
                                                'thehumaneleague', 'civicnation', 'catalyst']
                    if segment.lower() in common_company_indicators or len(segment) < 10:
                        continue

                title_segment = segment
                break

            if not title_segment:
                return None

            # Clean up the segment
            # Replace common separators with spaces
            title = re.sub(r'[-_+]', ' ', title_segment)

            # Remove file extensions
            title = re.sub(r'\.(pdf|doc|docx)$', '', title, flags=re.I)

            # Remove common suffixes like job IDs at the end
            title = re.sub(r'\s+\d+$', '', title)

            # Remove query parameters if any slipped through
            title = re.sub(r'\?.*$', '', title)

            # Remove common prefixes
            title = re.sub(r'^(job[\s-]*(announcement|posting|opening|description)[\s-]*)', '', title, flags=re.I)

            # Title case each word
            title = title.title()

            # Clean up spacing
            title = re.sub(r'\s+', ' ', title).strip()

            # Only return if it looks like a real title (has multiple words or is reasonably long)
            if len(title) > 10 or len(title.split()) > 1:
                return title

            return None

        except Exception:
            return None

    def _extract_jobs_from_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract jobs from links that look like job postings - Enhanced version"""
        jobs = []
        seen_urls = set()  # Track to avoid duplicates
        job_keywords = ['job', 'position', 'career', 'opening', 'vacancy', 'role', 'opportunity', 'apply', 'hiring', 'employment']

        # Exclude common non-job navigation keywords
        exclude_keywords = ['home', 'about', 'contact', 'privacy', 'terms', 'login', 'sign', 'search', 'filter', 'sort', 'category']

        # Generic link texts that should be replaced with URL-extracted titles
        generic_texts = ['apply now', 'apply', 'view job', 'learn more', 'read more', 'details', 'more info']

        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            full_url = urljoin(base_url, href)

            # Skip if already seen this URL
            if full_url in seen_urls:
                continue

            # Skip navigation/footer links
            if any(exclude in href.lower() or exclude in text.lower() for exclude in exclude_keywords):
                continue

            # Check if link text or href contains job-related keywords
            if any(keyword in href.lower() or keyword in text.lower() for keyword in job_keywords):
                if text and 5 < len(text) < 200:  # Reasonable title length
                    # Try to extract more context from parent element
                    parent = link.parent
                    description = None
                    location = None

                    if parent:
                        # Look for description in sibling or child elements
                        desc_elem = parent.find('p') or parent.find('div', class_=re.compile('desc|summary', re.I))
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)[:2000]

                        # Look for location
                        loc_elem = parent.find(class_=re.compile('location|city|region', re.I))
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)

                    # If title is generic (like "Apply Now"), try to extract from URL
                    title = text
                    if text.lower() in generic_texts:
                        url_title = self._extract_title_from_url(full_url)
                        if url_title:
                            title = url_title

                    jobs.append({
                        'title': title,
                        'url': full_url,
                        'description': description,
                        'location': location
                    })
                    seen_urls.add(full_url)

        return jobs

    def scrape_with_config(self, url: str, parser_config: Dict) -> List[Dict]:
        """
        Scrape jobs using a specific parser configuration

        Parser config format:
        {
            'job_container': {'tag': 'div', 'class': 'job-listing'},
            'title': {'tag': 'h3', 'class': 'job-title'},
            'url': {'tag': 'a', 'attr': 'href'},
            'location': {'tag': 'span', 'class': 'location'},
            'description': {'tag': 'p', 'class': 'description'}
        }

        OR for URL pattern matching:
        {
            'url_pattern': '/en/nonprofit-job/',
            'exclude_patterns': ['/apply', '/share']
        }
        """
        soup = self.fetch_page(url)
        if not soup:
            return []

        jobs = []
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Check if this is a URL pattern-based config
        if 'url_pattern' in parser_config:
            return self._scrape_by_url_pattern(soup, base_url, parser_config)

        # Find all job containers
        container_config = parser_config.get('job_container', {})
        containers = soup.find_all(
            container_config.get('tag', 'div'),
            class_=container_config.get('class')
        )

        for container in containers:
            job = {'url': url}  # Default to page URL

            # Extract each field based on config
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

            if job.get('title'):  # Only add if we found a title
                jobs.append(job)

        return jobs

    def _scrape_by_url_pattern(self, soup: BeautifulSoup, base_url: str, config: Dict) -> List[Dict]:
        """
        Scrape jobs by filtering links that match URL patterns
        Useful for sites where job URLs follow a specific pattern
        """
        jobs = []
        seen_urls = set()

        url_pattern = config.get('url_pattern', '')
        exclude_patterns = config.get('exclude_patterns', [])

        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']
            full_url = urljoin(base_url, href)

            # Skip if already seen
            if full_url in seen_urls:
                continue

            # Check if URL matches the pattern
            if url_pattern not in href:
                continue

            # Check exclude patterns
            if any(exclude in href for exclude in exclude_patterns):
                continue

            # Extract job info
            text = link.get_text(strip=True)
            if text and 5 < len(text) < 200:
                # Try to get more context from parent
                parent = link.parent
                description = None
                location = None

                if parent:
                    # Look for description nearby
                    desc_elem = parent.find('p') or parent.find('div', class_=re.compile('desc|summary|snippet', re.I))
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)[:2000]

                    # Look for location
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

    def test_selectors(self, url: str) -> Dict:
        """
        Test URL and return information about the page structure
        Helpful for debugging and creating parser configs
        """
        soup = self.fetch_page(url)
        if not soup:
            return {'error': 'Failed to fetch page'}

        info = {
            'title': soup.title.string if soup.title else 'No title',
            'common_classes': [],
            'common_tags': {},
            'links_count': len(soup.find_all('a')),
        }

        # Find most common classes
        all_classes = []
        for elem in soup.find_all(class_=True):
            all_classes.extend(elem.get('class', []))

        class_counts = {}
        for cls in all_classes:
            class_counts[cls] = class_counts.get(cls, 0) + 1

        # Get top 10 most common classes
        info['common_classes'] = sorted(
            class_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Count common tags
        for tag in ['div', 'article', 'section', 'li', 'tr']:
            info['common_tags'][tag] = len(soup.find_all(tag))

        return info
