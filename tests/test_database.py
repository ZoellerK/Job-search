"""Tests for database.py"""
import json
import os
import tempfile

import pytest

from database import JobDatabase


@pytest.fixture
def db(tmp_path):
    """Create a fresh in-memory-style DB for each test."""
    db_path = str(tmp_path / "test_jobs.db")
    return JobDatabase(db_path)


class TestAddAndRetrieve:
    def test_add_job_returns_true(self, db):
        assert db.add_job("TestSite", "https://example.com/job1", "Engineer")

    def test_duplicate_url_returns_false(self, db):
        db.add_job("TestSite", "https://example.com/job1", "Engineer")
        assert not db.add_job("TestSite", "https://example.com/job1", "Engineer")

    def test_get_recent_jobs(self, db):
        db.add_job("A", "https://a.com/1", "Title A")
        db.add_job("B", "https://b.com/1", "Title B")
        jobs = db.get_recent_jobs(limit=10)
        assert len(jobs) == 2
        # Most recent first
        titles = [j['title'] for j in jobs]
        assert "Title A" in titles
        assert "Title B" in titles

    def test_job_dict_keys(self, db):
        db.add_job("Site", "https://x.com/1", "T", description="desc",
                    location="NYC", salary="100k", job_type="Full-time")
        jobs = db.get_recent_jobs()
        job = jobs[0]
        for key in ['id', 'site_name', 'url', 'title', 'description',
                     'location', 'discovered_date', 'salary', 'job_type']:
            assert key in job, f"Missing key: {key}"
        assert job['description'] == "desc"
        assert job['salary'] == "100k"

    def test_job_exists(self, db):
        db.add_job("S", "https://x.com/1", "T")
        assert db.job_exists("https://x.com/1")
        assert not db.job_exists("https://x.com/nope")


class TestUpdateDetails:
    def test_update_sets_fields(self, db):
        db.add_job("S", "https://x.com/1", "T")
        updated = db.update_job_details("https://x.com/1", description="New desc",
                                        salary="120k")
        assert updated
        job = db.get_recent_jobs()[0]
        assert job['description'] == "New desc"
        assert job['salary'] == "120k"
        assert job['details_scraped']

    def test_update_nonexistent_returns_false(self, db):
        assert not db.update_job_details("https://nope.com", description="x")


class TestCrossSiteDedup:
    def test_finds_similar_title(self, db):
        db.add_job("SiteA", "https://a.com/1", "Senior Program Manager")
        match = db.find_similar_job("Senior Program Manager", "SiteB")
        assert match is not None
        assert match['site_name'] == "SiteA"

    def test_no_match_same_site(self, db):
        db.add_job("SiteA", "https://a.com/1", "Senior Program Manager")
        match = db.find_similar_job("Senior Program Manager", "SiteA")
        assert match is None

    def test_normalizes_case_and_punctuation(self, db):
        db.add_job("SiteA", "https://a.com/1", "Senior Program Manager")
        match = db.find_similar_job("SENIOR  program-Manager!", "SiteB")
        assert match is not None

    def test_short_titles_skipped(self, db):
        db.add_job("SiteA", "https://a.com/1", "Intern")
        match = db.find_similar_job("Intern", "SiteB")
        assert match is None  # Too short to reliably match


class TestSiteHealth:
    def test_record_and_retrieve(self, db):
        db.record_scrape_result("Site1", True, jobs_found=5)
        db.record_scrape_result("Site1", False, error_message="timeout")
        summary = db.get_site_health_summary()
        assert len(summary) == 1
        assert summary[0]['site_name'] == "Site1"
        assert summary[0]['successes'] == 1
        assert summary[0]['failures'] == 1

    def test_failing_sites_detection(self, db):
        for _ in range(3):
            db.record_scrape_result("BadSite", False, error_message="500")
        failing = db.get_failing_sites(consecutive_failures=3)
        assert len(failing) == 1
        assert failing[0]['site_name'] == "BadSite"

    def test_not_failing_if_recent_success(self, db):
        db.record_scrape_result("Site", False, error_message="err")
        db.record_scrape_result("Site", False, error_message="err")
        db.record_scrape_result("Site", True, jobs_found=1)
        failing = db.get_failing_sites(consecutive_failures=3)
        assert len(failing) == 0


class TestExport:
    def test_export_csv(self, db, tmp_path):
        db.add_job("S", "https://x.com/1", "Job One")
        db.add_job("S", "https://x.com/2", "Job Two")
        out = str(tmp_path / "export.csv")
        db.export_jobs(out, fmt="csv")
        with open(out) as f:
            content = f.read()
        assert "Job One" in content
        assert "Job Two" in content

    def test_export_json(self, db, tmp_path):
        db.add_job("S", "https://x.com/1", "Job One")
        out = str(tmp_path / "export.json")
        db.export_jobs(out, fmt="json")
        with open(out) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]['title'] == "Job One"

    def test_export_filtered_by_site(self, db, tmp_path):
        db.add_job("A", "https://a.com/1", "Job A")
        db.add_job("B", "https://b.com/1", "Job B")
        out = str(tmp_path / "export.json")
        db.export_jobs(out, fmt="json", site_name="A")
        with open(out) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]['site_name'] == "A"


class TestStats:
    def test_stats_structure(self, db):
        stats = db.get_stats()
        assert 'total_jobs' in stats
        assert 'jobs_today' in stats
        assert 'jobs_this_week' in stats
        assert 'total_sites' in stats

    def test_stats_counts(self, db):
        db.add_job("A", "https://a.com/1", "T1")
        db.add_job("B", "https://b.com/1", "T2")
        stats = db.get_stats()
        assert stats['total_jobs'] == 2
        assert stats['total_sites'] == 2


class TestStaleness:
    def test_add_job_sets_last_seen_date(self, db):
        db.add_job("S", "https://x.com/1", "T")
        job = db.get_recent_jobs()[0]
        assert job['last_seen_date'] is not None
        assert job['stale'] == 0

    def test_mark_jobs_seen_updates_date(self, db):
        db.add_job("S", "https://x.com/1", "T")
        original = db.get_recent_jobs()[0]['last_seen_date']
        import time; time.sleep(0.01)
        db.mark_jobs_seen(["https://x.com/1"])
        updated = db.get_recent_jobs()[0]['last_seen_date']
        assert updated >= original

    def test_mark_stale_jobs(self, db):
        db.add_job("S", "https://x.com/1", "Old Job")
        # Manually backdate the last_seen_date
        with db._connect() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen_date = datetime('now', '-60 days') WHERE url = ?",
                ("https://x.com/1",)
            )
            conn.commit()
        count = db.mark_stale_jobs(stale_after_days=30)
        assert count == 1
        stale = db.get_stale_jobs()
        assert len(stale) == 1
        assert stale[0]['title'] == "Old Job"

    def test_fresh_jobs_not_marked_stale(self, db):
        db.add_job("S", "https://x.com/1", "Fresh Job")
        count = db.mark_stale_jobs(stale_after_days=30)
        assert count == 0

    def test_mark_seen_clears_stale(self, db):
        db.add_job("S", "https://x.com/1", "Job")
        with db._connect() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen_date = datetime('now', '-60 days'), stale = 1 WHERE url = ?",
                ("https://x.com/1",)
            )
            conn.commit()
        db.mark_jobs_seen(["https://x.com/1"])
        job = db.get_recent_jobs()[0]
        assert job['stale'] == 0


class TestParserConfig:
    def test_save_and_load(self, db):
        config = {'job_container': {'tag': 'div', 'class': 'job'}}
        db.save_parser_config("TestSite", "https://test.com", config)
        loaded = db.get_parser_config("TestSite")
        assert loaded == config

    def test_missing_config_returns_none(self, db):
        assert db.get_parser_config("Nonexistent") is None
