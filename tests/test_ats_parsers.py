"""Tests for ats_parsers.py"""
import pytest
from bs4 import BeautifulSoup

from ats_parsers import (
    detect_ats, parse_greenhouse, parse_lever, parse_workable,
    parse_icims, parse_taleo, parse_workday, parse_adp, parse_applicantpro,
)


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

    def test_icims(self):
        assert detect_ats("https://interns-brookings.icims.com/jobs/intro") == "icims"

    def test_taleo(self):
        assert detect_ats("https://phe.tbe.taleo.net/phe01/ats/careers/v2/jobSearch") == "taleo"

    def test_workday(self):
        assert detect_ats("https://gatesfoundation.wd1.myworkdayjobs.com/en-US/Gates") == "workday"

    def test_adp(self):
        assert detect_ats("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html") == "adp"

    def test_applicantpro(self):
        assert detect_ats("https://carnegieendowment.applicantpro.com/jobs/") == "applicantpro"

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


ICIMS_HTML = """
<html><body>
<div class="iCIMS_JobsTable">
  <a href="/jobs/1234/job">Policy Research Associate</a>
  <span class="location">Washington, DC</span>
</div>
<div class="iCIMS_JobsTable">
  <a href="/jobs/5678/job">Communications Director</a>
  <span class="location">Remote</span>
</div>
</body></html>
"""


class TestParseIcims:
    def test_finds_jobs(self):
        soup = BeautifulSoup(ICIMS_HTML, 'lxml')
        jobs = parse_icims(soup, "https://interns-brookings.icims.com")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(ICIMS_HTML, 'lxml')
        jobs = parse_icims(soup, "https://interns-brookings.icims.com")
        titles = {j['title'] for j in jobs}
        assert "Policy Research Associate" in titles

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_icims(soup, "https://icims.com")
        assert jobs == []

    def test_skips_apply_links(self):
        html = """
        <html><body>
        <a href="/jobs/123/job">Real Job Title</a>
        <a href="/jobs/123/apply">Apply</a>
        </body></html>
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = parse_icims(soup, "https://icims.com")
        assert len(jobs) == 1
        assert jobs[0]['title'] == "Real Job Title"


TALEO_HTML = """
<html><body>
<table>
  <tr class="job-row">
    <td><a href="/requisition/12345">Senior Policy Analyst</a></td>
    <td>New York, NY</td>
  </tr>
  <tr class="job-row">
    <td><a href="/requisition/67890">Program Coordinator</a></td>
    <td>Washington, DC</td>
  </tr>
</table>
</body></html>
"""


class TestParseTaleo:
    def test_finds_jobs(self):
        soup = BeautifulSoup(TALEO_HTML, 'lxml')
        jobs = parse_taleo(soup, "https://phe.tbe.taleo.net")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(TALEO_HTML, 'lxml')
        jobs = parse_taleo(soup, "https://phe.tbe.taleo.net")
        titles = {j['title'] for j in jobs}
        assert "Senior Policy Analyst" in titles

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_taleo(soup, "https://taleo.net")
        assert jobs == []


WORKDAY_HTML = """
<html><body>
<ul>
  <li>
    <a data-automation-id="jobTitle" href="/job/12345">Grants Manager</a>
    <span data-automation-id="location">Seattle, WA</span>
    <span data-automation-id="postedOn">Posted 3 days ago</span>
  </li>
  <li>
    <a data-automation-id="jobTitle" href="/job/67890">Data Scientist</a>
    <span data-automation-id="location">Remote</span>
  </li>
</ul>
</body></html>
"""


class TestParseWorkday:
    def test_finds_jobs(self):
        soup = BeautifulSoup(WORKDAY_HTML, 'lxml')
        jobs = parse_workday(soup, "https://gatesfoundation.wd1.myworkdayjobs.com")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(WORKDAY_HTML, 'lxml')
        jobs = parse_workday(soup, "https://gatesfoundation.wd1.myworkdayjobs.com")
        titles = {j['title'] for j in jobs}
        assert "Grants Manager" in titles

    def test_extracts_location(self):
        soup = BeautifulSoup(WORKDAY_HTML, 'lxml')
        jobs = parse_workday(soup, "https://gatesfoundation.wd1.myworkdayjobs.com")
        gm = next(j for j in jobs if "Grants" in j['title'])
        assert gm['location'] == "Seattle, WA"

    def test_extracts_posted_date(self):
        soup = BeautifulSoup(WORKDAY_HTML, 'lxml')
        jobs = parse_workday(soup, "https://gatesfoundation.wd1.myworkdayjobs.com")
        gm = next(j for j in jobs if "Grants" in j['title'])
        assert "3 days ago" in gm['posted_date']

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_workday(soup, "https://myworkdayjobs.com")
        assert jobs == []

    def test_fallback_to_job_links(self):
        html = """
        <html><body>
        <a href="/job/111">Research Fellow</a>
        <a href="/job/222">Program Associate</a>
        <a href="/signin">Sign In</a>
        </body></html>
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = parse_workday(soup, "https://myworkdayjobs.com")
        assert len(jobs) == 2


APPLICANTPRO_HTML = """
<html><body>
<div class="job-listing">
  <a href="/jobs/1001/research-director">Research Director</a>
  <span class="location">Pittsburgh, PA</span>
  <span class="department">Policy</span>
</div>
<div class="job-listing">
  <a href="/jobs/1002/grants-writer">Grants Writer</a>
  <span class="location">Remote</span>
</div>
</body></html>
"""


class TestParseApplicantpro:
    def test_finds_jobs(self):
        soup = BeautifulSoup(APPLICANTPRO_HTML, 'lxml')
        jobs = parse_applicantpro(soup, "https://carnegieendowment.applicantpro.com")
        assert len(jobs) == 2

    def test_extracts_title(self):
        soup = BeautifulSoup(APPLICANTPRO_HTML, 'lxml')
        jobs = parse_applicantpro(soup, "https://carnegieendowment.applicantpro.com")
        titles = {j['title'] for j in jobs}
        assert "Research Director" in titles

    def test_extracts_location(self):
        soup = BeautifulSoup(APPLICANTPRO_HTML, 'lxml')
        jobs = parse_applicantpro(soup, "https://carnegieendowment.applicantpro.com")
        rd = next(j for j in jobs if "Research" in j['title'])
        assert rd['location'] == "Pittsburgh, PA"

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'lxml')
        jobs = parse_applicantpro(soup, "https://applicantpro.com")
        assert jobs == []

    def test_skips_generic_links(self):
        html = """
        <html><body>
        <a href="/jobs/123/real-job">Real Job Title Here</a>
        <a href="/jobs/123/apply">Apply</a>
        </body></html>
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = parse_applicantpro(soup, "https://applicantpro.com")
        assert len(jobs) == 1
