"""Tests for scraper.py — uses mocked HTTP to avoid real network calls."""
import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from scraper import JobScraper, DomainThrottler


@pytest.fixture
def scraper():
    return JobScraper(timeout=5, retry_attempts=2, domain_delay=0.0)


def _make_response(html_content: str, status_code: int = 200):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = html_content.encode('utf-8')
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


SAMPLE_CAREERS_PAGE = """
<html><body>
<div class="job-listing">
  <h3><a href="/careers/senior-engineer">Senior Engineer</a></h3>
  <span class="location">Remote</span>
  <p>Build cool stuff</p>
</div>
<div class="job-listing">
  <h3><a href="/careers/product-manager">Product Manager</a></h3>
  <span class="location">NYC</span>
</div>
</body></html>
"""

SAMPLE_LINK_PAGE = """
<html><body>
<a href="/jobs/program-director-of-operations">Program Director of Operations</a>
<a href="/about">About Us</a>
</body></html>
"""


class TestAutoDetectJobs:
    @patch.object(JobScraper, 'fetch_page')
    def test_detects_jobs_from_class_patterns(self, mock_fetch, scraper):
        from bs4 import BeautifulSoup
        mock_fetch.return_value = BeautifulSoup(SAMPLE_CAREERS_PAGE, 'lxml')

        jobs = scraper.auto_detect_jobs("https://example.com/careers")
        assert len(jobs) == 2
        titles = {j['title'] for j in jobs}
        assert 'Senior Engineer' in titles
        assert 'Product Manager' in titles

    @patch.object(JobScraper, 'fetch_page')
    def test_falls_back_to_link_extraction(self, mock_fetch, scraper):
        from bs4 import BeautifulSoup
        mock_fetch.return_value = BeautifulSoup(SAMPLE_LINK_PAGE, 'lxml')

        jobs = scraper.auto_detect_jobs("https://example.com/careers")
        assert len(jobs) >= 1
        assert any('Program Director' in j['title'] for j in jobs)

    @patch.object(JobScraper, 'fetch_page')
    def test_returns_none_on_fetch_failure(self, mock_fetch, scraper):
        mock_fetch.return_value = None
        result = scraper.auto_detect_jobs("https://example.com/careers")
        assert result is None


class TestFetchPage:
    @patch('scraper.requests.Session')
    def test_successful_fetch(self, mock_session_cls, scraper):
        mock_session = MagicMock()
        mock_session.get.return_value = _make_response("<html><body>Hello</body></html>")
        scraper._local.session = mock_session

        soup = scraper.fetch_page("https://example.com")
        assert soup is not None
        assert "Hello" in soup.get_text()

    @patch('scraper.requests.Session')
    def test_404_returns_none(self, mock_session_cls, scraper):
        mock_session = MagicMock()
        mock_session.get.return_value = _make_response("", 404)
        scraper._local.session = mock_session

        soup = scraper.fetch_page("https://example.com/nope")
        assert soup is None

    @patch('scraper.requests.Session')
    def test_retries_on_connection_error(self, mock_session_cls, scraper):
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            requests.ConnectionError("timeout"),
            _make_response("<html><body>OK</body></html>"),
        ]
        scraper._local.session = mock_session

        soup = scraper.fetch_page("https://example.com")
        assert soup is not None
        assert mock_session.get.call_count == 2


class TestExtractTitleFromUrl:
    def test_slug_to_title(self):
        s = JobScraper()
        assert s._extract_title_from_url("https://x.com/careers/program-partnerships-manager") == "Program Partnerships Manager"

    def test_pure_number_skipped(self):
        s = JobScraper()
        result = s._extract_title_from_url("https://x.com/jobs/12345")
        assert result is None

    def test_uuid_skipped(self):
        s = JobScraper()
        result = s._extract_title_from_url("https://x.com/jobs/abcdef12-3456-7890-abcd-ef1234567890")
        assert result is None


class TestDomainThrottler:
    def test_throttle_delays_requests(self):
        throttler = DomainThrottler(default_delay=0.1)
        start = time.monotonic()
        throttler.wait("example.com")
        throttler.wait("example.com")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1

    def test_different_domains_not_throttled(self):
        throttler = DomainThrottler(default_delay=0.5)
        start = time.monotonic()
        throttler.wait("a.com")
        throttler.wait("b.com")
        elapsed = time.monotonic() - start
        # Different domains shouldn't wait for each other
        assert elapsed < 0.5

    def test_429_increases_backoff(self):
        throttler = DomainThrottler(default_delay=1.0)
        throttler.record_429("slow.com")
        assert throttler._backoff["slow.com"] == 2.0
        throttler.record_429("slow.com")
        assert throttler._backoff["slow.com"] == 4.0


class TestIsLikelyJobTitle:
    def test_rejects_nav_links(self):
        s = JobScraper()
        assert not s._is_likely_job_title('About us')
        assert not s._is_likely_job_title('Our Approach')
        assert not s._is_likely_job_title('take action')
        assert not s._is_likely_job_title('Donate Now')
        assert not s._is_likely_job_title('Subscribe')
        assert not s._is_likely_job_title('Learn More')
        assert not s._is_likely_job_title('Find Out More')

    def test_rejects_boilerplate(self):
        s = JobScraper()
        assert not s._is_likely_job_title('Hiring Software')
        assert not s._is_likely_job_title('No jobs found - Filters applied')
        assert not s._is_likely_job_title('Applicant tracking system by Teamtailor')
        assert not s._is_likely_job_title('Jobs powered by Lever')
        assert not s._is_likely_job_title('Post a Job Listing')

    def test_rejects_email_addresses(self):
        s = JobScraper()
        assert not s._is_likely_job_title('applyhelp@tnc.org')

    def test_rejects_overly_long_titles(self):
        s = JobScraper()
        long_title = 'A' * 151
        assert not s._is_likely_job_title(long_title)

    def test_accepts_real_job_titles(self):
        s = JobScraper()
        assert s._is_likely_job_title('Senior Engineer')
        assert s._is_likely_job_title('Program Director of Operations')
        assert s._is_likely_job_title('Deputy Director, Regional Integration')
        assert s._is_likely_job_title('Product / Engineer / Data Roles')
        assert s._is_likely_job_title('Digital Media Intern')

    def test_rejects_empty(self):
        s = JobScraper()
        assert not s._is_likely_job_title('')
        assert not s._is_likely_job_title(None)
        assert not s._is_likely_job_title('   ')


class TestSanitizeDescription:
    def test_strips_cookie_consent(self):
        s = JobScraper()
        text = (
            "The technical storage or access is strictly necessary for the "
            "legitimate purpose of enabling the use of a specific service.\n\n"
            "We are looking for a Program Manager to lead our team."
        )
        result = s._sanitize_description(text)
        assert 'technical storage' not in result
        assert 'Program Manager' in result

    def test_preserves_clean_description(self):
        s = JobScraper()
        text = "We are looking for a talented engineer to join our team."
        result = s._sanitize_description(text)
        assert result == text

    def test_returns_none_for_all_boilerplate(self):
        s = JobScraper()
        text = "This website uses cookies to ensure you get the best experience."
        result = s._sanitize_description(text)
        assert result is None

    def test_returns_none_for_empty(self):
        s = JobScraper()
        assert s._sanitize_description('') == ''
        assert s._sanitize_description(None) is None


class TestAutoDetectFiltersJunk:
    @patch.object(JobScraper, 'fetch_page')
    def test_filters_nav_links_from_class_detection(self, mock_fetch, scraper):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
        <div class="opportunity">
          <h3><a href="/about">About us</a></h3>
        </div>
        <div class="opportunity">
          <h3><a href="/jobs/program-manager">Program Manager</a></h3>
        </div>
        <div class="opportunity">
          <h3><a href="/donate">Donate Now</a></h3>
        </div>
        </body></html>
        """
        mock_fetch.return_value = BeautifulSoup(html, 'lxml')
        jobs = scraper.auto_detect_jobs("https://example.com/careers")
        titles = [j['title'] for j in jobs]
        assert 'Program Manager' in titles
        assert 'About us' not in titles
        assert 'Donate Now' not in titles


class TestScrapeWithConfig:
    @patch.object(JobScraper, 'fetch_page')
    def test_custom_config_extraction(self, mock_fetch, scraper):
        from bs4 import BeautifulSoup
        html_content = """
        <html><body>
        <div class="opening">
          <h2 class="title">Data Analyst</h2>
          <a href="/apply/data-analyst">Apply</a>
        </div>
        </body></html>
        """
        mock_fetch.return_value = BeautifulSoup(html_content, 'lxml')

        config = {
            'job_container': {'tag': 'div', 'class': 'opening'},
            'title': {'tag': 'h2', 'class': 'title'},
            'url': {'tag': 'a', 'attr': 'href'},
        }
        jobs = scraper.scrape_with_config("https://example.com/jobs", config)
        assert len(jobs) == 1
        assert jobs[0]['title'] == 'Data Analyst'

    @patch.object(JobScraper, 'fetch_page')
    def test_returns_none_on_fetch_failure(self, mock_fetch, scraper):
        mock_fetch.return_value = None
        config = {
            'job_container': {'tag': 'div', 'class': 'opening'},
            'title': {'tag': 'h2', 'class': 'title'},
        }
        result = scraper.scrape_with_config("https://example.com/jobs", config)
        assert result is None
