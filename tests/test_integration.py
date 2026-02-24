"""Integration tests — full scrape-to-feed pipeline with mocked HTTP."""
import csv
import json
import os
import xml.etree.ElementTree as ET

import pytest
from unittest.mock import patch, MagicMock

from database import JobDatabase
from feed_generator import RSSFeedGenerator
from job_aggregator import JobAggregator


# ── Helpers ────────────────────────────────────────────────────────────

def _write_sites_csv(path, rows):
    """Write a sites.csv with the given list-of-dicts."""
    fieldnames = ['site_name', 'url', 'active', 'keywords', 'scrape_details']
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_config(path, db_path, feed_path):
    config = {
        'feed': {
            'title': 'Test Feed', 'description': 'Test', 'author': 'Test',
            'link': 'https://example.com/feed.xml',
            'include_site_in_title': True,
            'simple_descriptions': False,
            'include_summary': True,
        },
        'database': {'path': db_path},
        'output': {'feed_file': feed_path, 'max_items': 50},
        'scraping': {
            'user_agent': 'TestBot/1.0', 'timeout': 5,
            'retry_attempts': 1, 'max_workers': 2,
        },
        'logging': {'level': 'WARNING'},
        'cleanup': {'days_to_keep': 90, 'stale_after_days': 30},
    }
    with open(path, 'w') as f:
        json.dump(config, f)


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def workspace(tmp_path):
    """Set up a self-contained workspace with config, sites, and empty DB."""
    db_path = str(tmp_path / 'test.db')
    feed_path = str(tmp_path / 'feed.xml')
    config_path = str(tmp_path / 'config.json')
    sites_path = str(tmp_path / 'sites.csv')

    _write_config(config_path, db_path, feed_path)
    _write_sites_csv(sites_path, [
        {'site_name': 'Alpha Foundation', 'url': 'https://alpha.org/jobs',
         'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
        {'site_name': 'Beta Institute', 'url': 'https://beta.org/careers',
         'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
    ])

    return {
        'tmp_path': tmp_path,
        'db_path': db_path,
        'feed_path': feed_path,
        'config_path': config_path,
        'sites_path': sites_path,
    }


# ── Tests ──────────────────────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end: load sites → scrape (mocked) → store → generate feed."""

    def _mock_auto_detect(self, url):
        """Return fake jobs keyed by URL."""
        jobs_by_url = {
            'https://alpha.org/jobs': [
                {'title': 'Program Director', 'url': 'https://alpha.org/jobs/1',
                 'description': 'Lead grant-making strategy and advocacy programs.'},
                {'title': 'Research Analyst', 'url': 'https://alpha.org/jobs/2',
                 'description': 'Conduct policy research and analysis.'},
            ],
            'https://beta.org/careers': [
                {'title': 'Communications Manager', 'url': 'https://beta.org/careers/3',
                 'description': 'Manage external communications and partnerships.'},
            ],
        }
        return jobs_by_url.get(url, [])

    def test_scrape_stores_and_generates_feed(self, workspace):
        with patch('job_aggregator.JobScraper') as MockScraper:
            instance = MockScraper.return_value
            instance.auto_detect_jobs.side_effect = self._mock_auto_detect
            instance.fetch_page.return_value = None

            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
            results = agg.scrape_all()

        assert results['total_new_jobs'] == 3
        assert results['successful_sites'] == 2
        assert results['failed_sites'] == 0

        # Verify DB state
        jobs = agg.db.get_recent_jobs(limit=50)
        assert len(jobs) == 3
        titles = {j['title'] for j in jobs}
        assert titles == {'Program Director', 'Research Analyst', 'Communications Manager'}

        # Generate feed and verify XML
        agg.generate_feed()
        assert os.path.exists(workspace['feed_path'])
        tree = ET.parse(workspace['feed_path'])
        items = tree.findall('.//item')
        assert len(items) == 3

    def test_duplicate_urls_not_added_twice(self, workspace):
        with patch('job_aggregator.JobScraper') as MockScraper:
            instance = MockScraper.return_value
            instance.auto_detect_jobs.side_effect = self._mock_auto_detect
            instance.fetch_page.return_value = None

            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
            r1 = agg.scrape_all()
            r2 = agg.scrape_all()

        assert r1['total_new_jobs'] == 3
        assert r2['total_new_jobs'] == 0  # all duplicates
        assert len(agg.db.get_recent_jobs(limit=50)) == 3

    def test_feed_with_summary_and_health(self, workspace):
        with patch('job_aggregator.JobScraper') as MockScraper:
            instance = MockScraper.return_value
            instance.auto_detect_jobs.side_effect = self._mock_auto_detect
            instance.fetch_page.return_value = None

            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
            results = agg.scrape_all()
            alerts = agg.check_site_health()
            agg.generate_feed_with_summary(results, alerts)

        tree = ET.parse(workspace['feed_path'])
        items = tree.findall('.//item')
        # 3 jobs + 1 summary item
        assert len(items) == 4
        titles = [item.find('title').text for item in items]
        assert any('New Jobs' in t for t in titles)

    def test_stale_jobs_excluded_from_feed(self, workspace):
        with patch('job_aggregator.JobScraper') as MockScraper:
            instance = MockScraper.return_value
            instance.auto_detect_jobs.side_effect = self._mock_auto_detect
            instance.fetch_page.return_value = None

            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
            agg.scrape_all()

        # Manually mark one job as stale
        with agg.db._connect() as conn:
            conn.execute(
                "UPDATE jobs SET stale = 1, last_seen_date = datetime('now', '-60 days') "
                "WHERE title = 'Research Analyst'"
            )
            conn.commit()

        results = {'total_new_jobs': 0, 'successful_sites': 2,
                    'failed_sites': 0, 'site_results': []}
        agg.generate_feed_with_summary(results)

        tree = ET.parse(workspace['feed_path'])
        all_text = ET.tostring(tree.getroot(), encoding='unicode')
        assert 'Research Analyst' not in all_text


    def test_fetch_failure_recorded_as_failed(self, workspace):
        """When the scraper can't fetch a page, health should record failure."""
        def _mock_fail(url):
            return None  # fetch failure

        with patch('job_aggregator.JobScraper') as MockScraper:
            instance = MockScraper.return_value
            instance.auto_detect_jobs.side_effect = _mock_fail
            instance.fetch_page.return_value = None

            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
            results = agg.scrape_all()

        assert results['successful_sites'] == 0
        assert results['failed_sites'] == 2

        # Health records should show failure
        summary = agg.db.get_site_health_summary()
        for s in summary:
            assert s['failures'] > 0
            assert s['successes'] == 0


class TestCSVValidation:
    def test_missing_columns_returns_empty(self, workspace):
        # Write a CSV missing required columns
        with open(workspace['sites_path'], 'w') as f:
            f.write("name,link\nFoo,https://foo.com\n")

        with patch('job_aggregator.JobScraper'):
            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
        sites = agg.load_sites()
        assert sites == []

    def test_empty_url_skipped(self, workspace):
        _write_sites_csv(workspace['sites_path'], [
            {'site_name': 'Good', 'url': 'https://good.org/jobs',
             'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
            {'site_name': 'Bad', 'url': '',
             'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
        ])

        with patch('job_aggregator.JobScraper'):
            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
        sites = agg.load_sites()
        assert len(sites) == 1
        assert sites[0]['site_name'] == 'Good'

    def test_duplicate_urls_skipped(self, workspace):
        _write_sites_csv(workspace['sites_path'], [
            {'site_name': 'First', 'url': 'https://example.com/jobs',
             'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
            {'site_name': 'Dupe', 'url': 'https://example.com/jobs',
             'active': 'yes', 'keywords': '', 'scrape_details': 'no'},
        ])

        with patch('job_aggregator.JobScraper'):
            agg = JobAggregator(
                config_file=workspace['config_path'],
                sites_file=workspace['sites_path'],
            )
        sites = agg.load_sites()
        assert len(sites) == 1
        assert sites[0]['site_name'] == 'First'


class TestConfigDefaults:
    def test_minimal_config_uses_defaults(self, tmp_path):
        config_path = str(tmp_path / 'config.json')
        with open(config_path, 'w') as f:
            json.dump({'database': {'path': str(tmp_path / 'test.db')}}, f)

        sites_path = str(tmp_path / 'sites.csv')
        _write_sites_csv(sites_path, [])

        with patch('job_aggregator.JobScraper'):
            agg = JobAggregator(config_file=config_path, sites_file=sites_path)

        # Should have all defaults filled in
        assert agg.config['scraping']['timeout'] == 15
        assert agg.config['scraping']['max_workers'] == 5
        assert agg.config['output']['max_items'] == 100
        assert agg.config['cleanup']['days_to_keep'] == 90
        assert agg.config['cleanup']['stale_after_days'] == 30

    def test_invalid_json_exits(self, tmp_path):
        config_path = str(tmp_path / 'config.json')
        with open(config_path, 'w') as f:
            f.write("{bad json")

        with pytest.raises(SystemExit):
            JobAggregator(config_file=config_path)


class TestDatabaseIndexes:
    def test_indexes_exist(self, tmp_path):
        db = JobDatabase(str(tmp_path / 'test.db'))
        with db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row['name'] for row in cursor.fetchall()}

        assert 'idx_jobs_site_name' in indexes
        assert 'idx_jobs_discovered_date' in indexes
        assert 'idx_jobs_stale' in indexes
        assert 'idx_jobs_site_discovered' in indexes
        assert 'idx_site_health_site_date' in indexes
