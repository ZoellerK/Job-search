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
                return BeautifulSoup(response.content, 'html.parser')
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
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Common patterns for job listings
        job_patterns = [
            {'container': 'div', 'class_patterns': ['job', 'position', 'opening', 'listing', 'career']},
            {'container': 'li', 'class_patterns': ['job', 'position', 'opening', 'listing']},
            {'container': 'article', 'class_patterns': ['job', 'position', 'opening']},
            {'container': 'tr', 'class_patterns': ['job', 'position', 'opening']},
        ]

        # Try each pattern
        for pattern in job_patterns:
            containers = soup.find_all(pattern['container'])
            for container in containers:
                # Check if any class contains job-related keywords
                classes = container.get('class', [])
                if any(keyword in ' '.join(classes).lower() for keyword in pattern['class_patterns']):
                    job = self._extract_job_from_element(container, base_url)
                    if job and job.get('title'):
                        jobs.append(job)

        # If no jobs found with class patterns, look for common link patterns
        if not jobs:
            jobs = self._extract_jobs_from_links(soup, base_url)

        return jobs

    def _extract_job_from_element(self, element, base_url: str) -> Dict:
        """Extract job information from a DOM element"""
        job = {}

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

    def _extract_jobs_from_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract jobs from links that look like job postings"""
        jobs = []
        job_keywords = ['job', 'position', 'career', 'opening', 'vacancy', 'role', 'opportunity']

        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)

            # Check if link text or href contains job-related keywords
            if any(keyword in href.lower() or keyword in text.lower() for keyword in job_keywords):
                if text and len(text) > 5:  # Avoid empty or very short links
                    jobs.append({
                        'title': text,
                        'url': urljoin(base_url, href),
                        'description': None,
                        'location': None
                    })

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
        """
        soup = self.fetch_page(url)
        if not soup:
            return []

        jobs = []
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

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
