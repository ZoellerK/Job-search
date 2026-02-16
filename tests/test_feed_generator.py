"""Tests for feed_generator.py"""
import os
import xml.etree.ElementTree as ET

import pytest

from feed_generator import RSSFeedGenerator


@pytest.fixture
def feed_gen():
    return RSSFeedGenerator(
        title="Test Feed",
        description="Test description",
        link="https://example.com/feed.xml",
        author="Test",
    )


SAMPLE_JOBS = [
    {
        'title': 'Senior Engineer',
        'url': 'https://example.com/jobs/1',
        'site_name': 'TestCo',
        'description': 'Build things',
        'location': 'Remote',
        'discovered_date': '2025-01-15T10:00:00+00:00',
        'keywords': 'python,remote',
        'salary': '120k',
        'job_type': 'Full-time',
    },
    {
        'title': 'Product Manager',
        'url': 'https://example.com/jobs/2',
        'site_name': 'OtherCo',
        'description': None,
        'location': None,
        'discovered_date': '2025-01-14T10:00:00+00:00',
        'keywords': None,
        'salary': None,
        'job_type': None,
    },
]


class TestGenerateFeed:
    def test_creates_valid_xml(self, feed_gen, tmp_path):
        out = str(tmp_path / "feed.xml")
        feed_gen.generate_feed(SAMPLE_JOBS, out)
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == 'rss'
        assert root.get('version') == '2.0'

    def test_contains_all_jobs(self, feed_gen, tmp_path):
        out = str(tmp_path / "feed.xml")
        feed_gen.generate_feed(SAMPLE_JOBS, out)
        with open(out) as f:
            content = f.read()
        assert 'Senior Engineer' in content
        assert 'Product Manager' in content

    def test_includes_site_in_title_when_configured(self, tmp_path):
        gen = RSSFeedGenerator(include_site_in_title=True)
        out = str(tmp_path / "feed.xml")
        gen.generate_feed(SAMPLE_JOBS, out)
        with open(out) as f:
            content = f.read()
        assert 'TestCo' in content

    def test_simple_descriptions_mode(self, tmp_path):
        gen = RSSFeedGenerator(simple_descriptions=True)
        out = str(tmp_path / "feed.xml")
        gen.generate_feed(SAMPLE_JOBS, out)
        with open(out) as f:
            content = f.read()
        # Should NOT have content:encoded elements
        assert 'content:encoded' not in content


class TestBuildSummaryItem:
    def test_summary_basic(self, feed_gen):
        results = {
            'total_new_jobs': 5,
            'successful_sites': 10,
            'failed_sites': 2,
            'site_results': [
                {'site_name': 'A', 'success': True, 'new_jobs': 3, 'error': None},
                {'site_name': 'B', 'success': True, 'new_jobs': 2, 'error': None},
                {'site_name': 'C', 'success': False, 'new_jobs': 0, 'error': 'timeout'},
                {'site_name': 'D', 'success': False, 'new_jobs': 0, 'error': '404'},
            ]
        }
        item = feed_gen.build_summary_item(results)
        assert '5 New Jobs' in item['title']
        assert 'C' in item['description']

    def test_summary_includes_health_alerts(self, feed_gen):
        results = {
            'total_new_jobs': 0,
            'successful_sites': 5,
            'failed_sites': 0,
            'site_results': [],
        }
        alerts = [
            {'site_name': 'BrokenSite', 'consecutive_failures': 4,
             'last_error': 'Connection refused', 'last_attempt': '2025-01-15'},
        ]
        item = feed_gen.build_summary_item(results, health_alerts=alerts)
        assert 'BrokenSite' in item['description']
        assert 'Site Health Alerts' in item['description']
        assert '1 site alert' in item['title']


class TestHtmlPreview:
    def test_creates_html_file(self, feed_gen, tmp_path):
        out = str(tmp_path / "preview.html")
        feed_gen.generate_html_preview(SAMPLE_JOBS, out)
        assert os.path.exists(out)
        with open(out) as f:
            content = f.read()
        assert 'Senior Engineer' in content
        assert '<html>' in content


class TestMetadataExtraction:
    def test_remote_detection(self, feed_gen):
        job = {'title': 'Remote Engineer', 'description': '', 'location': 'Remote',
               'job_type': ''}
        cats = feed_gen._extract_job_metadata(job)
        assert 'Remote' in cats

    def test_seniority_detection(self, feed_gen):
        job = {'title': 'Senior Director of Ops', 'description': '',
               'location': '', 'job_type': ''}
        cats = feed_gen._extract_job_metadata(job)
        assert 'Senior' in cats
        assert 'Leadership' in cats

    def test_handles_none_values(self, feed_gen):
        job = {'title': None, 'description': None, 'location': None, 'job_type': None}
        cats = feed_gen._extract_job_metadata(job)
        assert isinstance(cats, list)
