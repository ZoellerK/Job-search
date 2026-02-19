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


    def test_summary_rich_content_is_raw_html(self, feed_gen):
        """Summary _rich_content should contain raw HTML, not escaped HTML."""
        results = {
            'total_new_jobs': 10,
            'successful_sites': 5,
            'failed_sites': 0,
            'site_results': [
                {'site_name': 'A', 'success': True, 'new_jobs': 10, 'error': None},
            ]
        }
        item = feed_gen.build_summary_item(results)
        # _rich_content should have actual HTML tags
        assert '<h3>' in item['_rich_content']
        assert '<strong>' in item['_rich_content']
        # description should be plain text (no HTML)
        assert '<h3>' not in item['description']
        assert 'New Jobs Found: 10' in item['description']

    def test_summary_no_double_escaping_in_feed(self, feed_gen, tmp_path):
        """Summary content:encoded should not have double-escaped HTML."""
        results = {
            'total_new_jobs': 5,
            'successful_sites': 3,
            'failed_sites': 0,
            'site_results': [
                {'site_name': 'TestOrg', 'success': True, 'new_jobs': 5, 'error': None},
            ]
        }
        item = feed_gen.build_summary_item(results)
        out = str(tmp_path / "feed.xml")
        feed_gen.generate_feed([item], out)
        with open(out) as f:
            content = f.read()
        # Should NOT contain double-escaped entities like &amp;lt;
        assert '&amp;lt;' not in content


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


class TestRelevanceScoring:
    def test_high_relevance_multiple_keywords(self, feed_gen):
        job = {'title': 'Director of Program Strategy', 'description': 'policy research grants'}
        result = feed_gen._score_relevance(job)
        assert result == 'Relevance: High'

    def test_medium_relevance_one_high_keyword(self, feed_gen):
        job = {'title': 'Research Intern', 'description': 'administrative support'}
        result = feed_gen._score_relevance(job)
        assert result == 'Relevance: Medium'

    def test_medium_relevance_two_medium_keywords(self, feed_gen):
        job = {'title': 'Communications Coordinator', 'description': ''}
        result = feed_gen._score_relevance(job)
        assert result == 'Relevance: Medium'

    def test_no_relevance_unrelated(self, feed_gen):
        job = {'title': 'Janitor', 'description': 'cleaning and maintenance'}
        result = feed_gen._score_relevance(job)
        assert result == ''

    def test_no_relevance_empty(self, feed_gen):
        job = {'title': '', 'description': ''}
        result = feed_gen._score_relevance(job)
        assert result == ''

    def test_relevance_in_metadata(self, feed_gen):
        job = {'title': 'Director of Program Strategy and Policy',
               'description': 'grants management', 'location': 'DC', 'job_type': 'Full-time'}
        cats = feed_gen._extract_job_metadata(job)
        assert 'Relevance: High' in cats

    def test_custom_keywords(self):
        gen = RSSFeedGenerator(relevance_keywords={
            'high': ['underwater', 'basket'],
            'medium': ['weaving'],
        })
        job = {'title': 'Underwater Basket Weaving Instructor', 'description': ''}
        result = gen._score_relevance(job)
        assert result == 'Relevance: High'
