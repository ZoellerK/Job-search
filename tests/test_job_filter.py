"""Tests for job_filter.py — examples taken from real scraped junk."""
import pytest

from job_filter import classify_job, filter_jobs, is_likely_job


def job(title, url):
    return {'title': title, 'url': url}


class TestRejectsNavigationPages:
    @pytest.mark.parametrize("title,url", [
        ("About us", "https://co-impact.org/about-us/"),
        ("Take action", "https://co-impact.org/take-action/"),
        ("Our approach", "https://co-impact.org/our-approach/"),
        ("Impact", "https://co-impact.org/impact/"),
        ("Donate Now", "https://www.classy.org/give/410226/#!/donation/checkout"),
        ("Subscribe", "https://mailchi.mp/protectdemocracy/hiring-updates"),
        ("No jobs found", "https://founderspledge.teamtailor.com/en-GB/connect"),
        ("DOWNLOAD PDF", "https://oakfnd.org/wp-content/uploads/2023/03/guide.pdf"),
        ("Post a Job Listing", "https://www.idealist.org/organization"),
    ])
    def test_navigation_titles_rejected(self, title, url):
        assert not is_likely_job(job(title, url))

    def test_homepage_link_rejected(self):
        assert not is_likely_job(job("Election Protection", "https://statesunited.org/"))
        assert not is_likely_job(job("Come and workwith us", "https://oakfnd.org/"))

    def test_careers_index_pages_rejected(self):
        # Careers landing pages are not specific postings
        assert not is_likely_job(job("Careers", "https://www.razomforukraine.org/careers/"))
        assert not is_likely_job(job("Careers", "https://www.berggruen.org/careers"))
        assert not is_likely_job(job("Open Positions", "https://protectdemocracy.org/#jobs-c88dea0d"))


class TestRejectsArticlesAndPrograms:
    @pytest.mark.parametrize("title,url", [
        ("Keep the defenders of Ukraine warm",
         "https://unitedhelpukraine.org/reports/keep-the-defenders-of-ukraine-warm/"),
        ("Defender's Aid", "https://unitedhelpukraine.org/programs/defenders-aid/"),
        ("Mental Wellness", "https://unitedhelpukraine.org/projects/mental-wellness/"),
        ("Ukrainian band Probass ∆ Hardi",
         "https://www.kissfm.ua/news/1006750-probass-hardi/"),
        ("FIND OUT MORE", "https://oakfnd.org/bringing-hidden-homelessness-into-the-light/"),
    ])
    def test_article_pages_rejected(self, title, url):
        assert not is_likely_job(job(title, url))

    def test_paragraph_title_rejected(self):
        # Sentence text: the salvaged leading fragment is itself junk ("Open Positions")
        long_title = ("Open PositionsAt Eurasia Foundation, we believe that when we "
                      "bring our authentic selves to work, we are happier and more capable.")
        assert not is_likely_job(job(long_title, "https://www.eurasia.org/contact/"))

    def test_long_title_without_boundary_rejected(self):
        long_title = "we believe that when we bring our authentic selves to work " * 3
        assert not is_likely_job(job(long_title, "https://example.org/positions/x"))

    def test_ats_vendor_marketing_page_rejected(self):
        assert not is_likely_job(job(
            "Applicant tracking systemby Teamtailor",
            "https://www.teamtailor.com/?utm_campaign=poweredby"))


class TestKeepsRealJobs:
    @pytest.mark.parametrize("title,url", [
        ("Chief Impact Officer", "https://protectdemocracy.org/o/chief-impact-officer"),
        ("Product / Engineer / Data Roles (Talent Community)",
         "https://protectdemocracy.org/o/product-engineer-data-roles-talent-community"),
        ("Vice President of Development",
         "https://www.razomforukraine.org/careers/vice-president-of-development"),
        ("Head of Development Operations",
         "https://www.longview.org/careers/head-of-development-operations/"),
        ("Senior Program Officer", "https://example.org/jobs/senior-program-officer"),
    ])
    def test_real_postings_kept(self, title, url):
        assert is_likely_job(job(title, url))

    def test_generic_cta_kept_when_url_is_specific_posting(self):
        # Scraper grabbed the button text, but the URL is a real posting
        assert is_likely_job(job("View job", "https://protectdemocracy.org/o/it-specialist-2"))
        assert is_likely_job(job("Careers", "https://www.on-ramps.com/jobs/3554"))
        assert is_likely_job(job(
            "Full-time positions", "https://job-boards.greenhouse.io/givewell/jobs/5015528008"))
        assert is_likely_job(job(
            "See full description and apply",
            "https://www.longview.org/careers/account-manager-advising/"))
        assert is_likely_job(job("Apply Now", "https://mfbl.bamboohr.com/careers/82?source=x"))
        assert is_likely_job(job(
            "Apply Now", "https://stand-up-america.breezy.hr/p/fe6447fecd0d-director-of-digital"))
        assert is_likely_job(job(
            "Apply Here!", "https://cepa.org/program-officer-communications-publications/"))

    def test_job_board_card_title_salvaged(self):
        # Idealist-style cards run title+org+location together; the real
        # title is recovered and the job kept
        card = ("Think 100% Campaigns ManagerHip Hop CaucusRemoteUnited States"
                "Full TimeUSD\xa0$70,000 - $94,000 / yearPosted 10 hours ago")
        j = job(card, "https://www.idealist.org/en/nonprofit-job/abc123-campaigns-manager")
        assert is_likely_job(j)
        kept, _ = filter_jobs([j])
        assert kept[0]['title'] == "Think 100% Campaigns Manager"

    def test_role_word_overrides_junk_path(self):
        # A real posting filed under a junky path segment
        assert is_likely_job(job(
            "Program Officer, Democracy", "https://example.org/news/program-officer-democracy"))

    def test_ats_subdomain_boards_kept(self):
        assert is_likely_job(job(
            "Research Analyst", "https://founderspledge.teamtailor.com/jobs/123-research-analyst"))


class TestClassifyAndFilter:
    def test_missing_fields_rejected(self):
        assert not is_likely_job({'title': '', 'url': 'https://example.org/jobs/1'})
        assert not is_likely_job({'title': 'Director', 'url': ''})
        assert not is_likely_job({})

    def test_classify_gives_reason(self):
        ok, reason = classify_job(job("Donate Now", "https://example.org/donate"))
        assert not ok
        assert reason

    def test_filter_jobs_splits_and_annotates(self):
        jobs = [
            job("Chief Impact Officer", "https://protectdemocracy.org/o/chief-impact-officer"),
            job("About us", "https://co-impact.org/about-us/"),
        ]
        kept, rejected = filter_jobs(jobs)
        assert len(kept) == 1
        assert kept[0]['title'] == "Chief Impact Officer"
        assert len(rejected) == 1
        assert rejected[0]['filter_reason']

    def test_filter_jobs_does_not_mutate_kept_jobs(self):
        jobs = [job("Director of Policy", "https://example.org/jobs/director-of-policy")]
        kept, rejected = filter_jobs(jobs)
        assert 'filter_reason' not in kept[0]
        assert rejected == []
