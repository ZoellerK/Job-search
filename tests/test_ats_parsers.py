"""Tests for ats_parsers.py"""
import pytest
from bs4 import BeautifulSoup

from ats_parsers import detect_ats, parse_greenhouse, parse_lever, parse_workable


class TestDetectAts:
    def test_greenhouse_board(self):
        assert detect_ats("https://job-boards.greenhouse.io/omidyarnetwork") == "greenhouse"

    def test_greenhouse_boards_variant(self):
        assert detect_ats("https://boards.greenhouse.io/someorg") == "greenhouse"

    def test_lever(self):
        assert detect_ats("https://jobs.lever.co/representus") == "lever"

    def test_workable(self):
        assert detect_ats("https://apply.workable.com/echoing-green/") == "workable"

    def test_teamtailor(self):
        assert detect_ats("https://founderspledge.teamtailor.com/en-GB/jobs") == "teamtailor"

    def test_unknown_returns_none(self):
        assert detect_ats("https://example.com/careers") is None

    def test_generic_nonprofit_returns_none(self):
        assert detect_ats("https://www.commoncause.org/careers/") is None


GREENHOUSE_HTML = """
<html><body>
<section class="level-0">
  <h2>Engineering</h2>
  <div class="opening">
    <a href="/omidyarnetwork/jobs/123">Senior Software Engineer</a>
    <span class="location">San Francisco, CA</span>
  </div>
  <div class="opening">
    <a href="/omidyarnetwork/jobs/456">Data Analyst</a>
    <span class="location">Remote</span>
  </div>
</section>
<section class="level-0">
  <h2>Operations</h2>
  <div class="opening">
    <a href="/omidyarnetwork/jobs/789">Office Manager</a>
    <span class="location">Redwood City, CA</span>
  </div>
</section>
</body></html>
"""


class TestParseGreenhouse:
    def test_finds_all_openings(self):
        soup = BeautifulSoup(GREENHOUSE_HTML, 'lxml')
        jobs = parse_greenhouse(soup, "https://job-boards.greenhouse.io")
        assert len(jobs) == 3

    def test_extracts_title_and_url(self):
        soup = BeautifulSoup(GREENHOUSE_HTML, 'lxml')
        jobs = parse_greenhouse(soup, "https://job-boards.greenhouse.io")
        eng = next(j for j in jobs if "Software" in j['title'])
        assert eng['title'] == "Senior Software Engineer"
        assert "/jobs/123" in eng['url']

    def test_extracts_location(self):
        soup = BeautifulSoup(GREENHOUSE_HTML, 'lxml')
        jobs = parse_greenhouse(soup, "https://job-boards.greenhouse.io")
        remote_job = next(j for j in jobs if "Data" in j['title'])
        assert remote_job['location'] == "Remote"

    def test_extracts_department(self):
        soup = BeautifulSoup(GREENHOUSE_HTML, 'lxml')
        jobs = parse_greenhouse(soup, "https://job-boards.greenhouse.io")
        eng = next(j for j in jobs if "Software" in j['title'])
        assert eng.get('department') == "Engineering"

    def test_deduplicates_urls(self):
        html = """
        <html><body>
        <div class="opening"><a href="/jobs/123">Job A</a></div>
        <div class="opening"><a href="/jobs/123">Job A Duplicate</a></div>
        </body></html>
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = parse_greenhouse(soup, "https://boards.greenhouse.io")
        assert len(jobs) == 1

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_greenhouse(soup, "https://boards.greenhouse.io")
        assert jobs == []


LEVER_HTML = """
<html><body>
<div class="posting">
  <a class="posting-title" href="https://jobs.lever.co/org/uuid-1">
    <h5>Program Manager</h5>
    <span class="sort-by-location posting-category small-category-label location">Washington, DC</span>
    <span class="sort-by-commitment posting-category small-category-label commitment">Full-time</span>
  </a>
</div>
<div class="posting">
  <a class="posting-title" href="https://jobs.lever.co/org/uuid-2">
    <h5>Research Analyst</h5>
    <span class="sort-by-location posting-category small-category-label location">Remote</span>
    <span class="sort-by-commitment posting-category small-category-label commitment">Part-time</span>
  </a>
</div>
</body></html>
"""


class TestParseLever:
    def test_finds_all_postings(self):
        soup = BeautifulSoup(LEVER_HTML, 'lxml')
        jobs = parse_lever(soup, "https://jobs.lever.co/org")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(LEVER_HTML, 'lxml')
        jobs = parse_lever(soup, "https://jobs.lever.co/org")
        titles = {j['title'] for j in jobs}
        assert "Program Manager" in titles
        assert "Research Analyst" in titles

    def test_extracts_location(self):
        soup = BeautifulSoup(LEVER_HTML, 'lxml')
        jobs = parse_lever(soup, "https://jobs.lever.co/org")
        pm = next(j for j in jobs if "Program" in j['title'])
        assert pm['location'] == "Washington, DC"

    def test_extracts_job_type(self):
        soup = BeautifulSoup(LEVER_HTML, 'lxml')
        jobs = parse_lever(soup, "https://jobs.lever.co/org")
        analyst = next(j for j in jobs if "Analyst" in j['title'])
        assert analyst['job_type'] == "Part-time"

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_lever(soup, "https://jobs.lever.co/org")
        assert jobs == []


WORKABLE_HTML = """
<html><body>
<li data-ui="job">
  <a href="/echoing-green/j/ABCD1234/">
    <h3 class="job-title">Fellowship Coordinator</h3>
    <span class="location">New York, NY</span>
  </a>
</li>
<li data-ui="job">
  <a href="/echoing-green/j/EFGH5678/">
    <h3 class="job-title">Communications Associate</h3>
    <span class="location">Remote</span>
  </a>
</li>
</body></html>
"""


class TestParseWorkable:
    def test_finds_jobs(self):
        soup = BeautifulSoup(WORKABLE_HTML, 'lxml')
        jobs = parse_workable(soup, "https://apply.workable.com")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(WORKABLE_HTML, 'lxml')
        jobs = parse_workable(soup, "https://apply.workable.com")
        titles = {j['title'] for j in jobs}
        assert "Fellowship Coordinator" in titles

    def test_extracts_location(self):
        soup = BeautifulSoup(WORKABLE_HTML, 'lxml')
        jobs = parse_workable(soup, "https://apply.workable.com")
        coord = next(j for j in jobs if "Coordinator" in j['title'])
        assert coord['location'] == "New York, NY"

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_workable(soup, "https://apply.workable.com")
        assert jobs == []

    def test_fallback_to_j_links(self):
        html = """
        <html><body>
        <a href="/org/j/ABC123/">Grant Writer</a>
        <a href="/org/j/DEF456/">Program Officer</a>
        </body></html>
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = parse_workable(soup, "https://apply.workable.com")
        assert len(jobs) == 2
