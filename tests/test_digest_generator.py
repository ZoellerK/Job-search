"""Tests for digest_generator.py and the aggregator digest command."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from digest_generator import build_digest, build_ntfy_message, send_ntfy


SAMPLE_JOBS = [
    {
        'title': 'Director of Public Policy',
        'url': 'https://example.org/jobs/director-of-public-policy',
        'site_name': 'Example Org',
        'location': 'Washington, DC',
        'salary': '$120,000 - $150,000',
        'description': 'Lead our public policy and advocacy strategy team.',
    },
    {
        'title': 'Office Cleaner',
        'url': 'https://example.org/jobs/office-cleaner',
        'site_name': 'Example Org',
        'description': 'Keep the office tidy.',
    },
]


class TestBuildDigest:
    def test_contains_jobs_and_links(self):
        md = build_digest(SAMPLE_JOBS, hours=24)
        assert '2 new jobs' in md
        assert '[Director of Public Policy](https://example.org/jobs/director-of-public-policy)' in md
        assert 'Washington, DC' in md
        assert '$120,000 - $150,000' in md

    def test_singular_job_count(self):
        md = build_digest(SAMPLE_JOBS[:1], hours=24)
        assert '1 new job in the last 24h' in md

    def test_relevance_grouping(self):
        def score(job):
            return 'Relevance: High' if 'Policy' in job['title'] else ''

        md = build_digest(SAMPLE_JOBS, hours=24, score_fn=score)
        high_pos = md.index('High relevance')
        other_pos = md.index('Other new listings')
        assert high_pos < other_pos
        assert md.index('Director of Public Policy') < other_pos
        assert md.index('Office Cleaner') > other_pos

    def test_footer_filtered_count_and_dashboard(self):
        md = build_digest(SAMPLE_JOBS, hours=24, filtered_count=7,
                          dashboard_url='https://example.github.io/jobs/')
        assert '7 obvious non-job links filtered out' in md
        assert '[Full dashboard](https://example.github.io/jobs/)' in md

    def test_no_footer_when_nothing_to_say(self):
        md = build_digest(SAMPLE_JOBS, hours=24)
        assert '---' not in md


class TestNtfy:
    def test_message_lists_jobs_and_truncates(self):
        jobs = [{'title': f'Job {i}', 'site_name': 'Org'} for i in range(10)]
        msg = build_ntfy_message(jobs, max_listed=6)
        assert '• Job 0 (Org)' in msg
        assert 'Job 6' not in msg
        assert '…and 4 more' in msg

    @patch('digest_generator.requests.post')
    def test_send_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert send_ntfy('my-topic', 'Title', 'Body', click_url='https://x.test')
        args, kwargs = mock_post.call_args
        assert args[0] == 'https://ntfy.sh/my-topic'
        assert kwargs['headers']['Title'] == 'Title'
        assert kwargs['headers']['Click'] == 'https://x.test'

    @patch('digest_generator.requests.post')
    def test_send_failure_returns_false(self, mock_post):
        import requests as _requests
        mock_post.side_effect = _requests.ConnectionError("boom")
        assert not send_ntfy('my-topic', 'Title', 'Body')


class TestGenerateDigestCommand:
    @pytest.fixture
    def aggregator(self, tmp_path, monkeypatch):
        from job_aggregator import JobAggregator
        config = {
            'feed': {'link': 'https://example.github.io/jobs/feed.xml'},
            'database': {'path': str(tmp_path / 'test.db')},
        }
        config_file = tmp_path / 'config.json'
        config_file.write_text(json.dumps(config))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv('NTFY_TOPIC', raising=False)
        return JobAggregator(config_file=str(config_file),
                             sites_file=str(tmp_path / 'sites.csv'))

    def test_digest_includes_new_real_jobs_only(self, aggregator, tmp_path):
        aggregator.db.add_job(
            site_name='Example Org',
            url='https://example.org/jobs/policy-director',
            title='Policy Director',
        )
        aggregator.db.add_job(
            site_name='Example Org',
            url='https://example.org/about-us/',
            title='About us',
        )
        count = aggregator.generate_digest(hours=24, output_file='digest.md')
        assert count == 1
        content = (tmp_path / 'digest.md').read_text()
        assert 'Policy Director' in content
        assert 'About us' not in content
        assert '1 obvious non-job link filtered out' in content

    def test_no_digest_file_when_no_new_jobs(self, aggregator, tmp_path):
        (tmp_path / 'digest.md').write_text('leftover from previous run')
        count = aggregator.generate_digest(hours=24, output_file='digest.md')
        assert count == 0
        assert not (tmp_path / 'digest.md').exists()

    def test_old_jobs_excluded(self, aggregator, tmp_path):
        old_date = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        with aggregator.db._connect() as conn:
            conn.execute("""
                INSERT INTO jobs (site_name, url, title, discovered_date)
                VALUES (?, ?, ?, ?)
            """, ('Example Org', 'https://example.org/jobs/old-role',
                  'Old Role Director', old_date))
            conn.commit()
        count = aggregator.generate_digest(hours=24, output_file='digest.md')
        assert count == 0
