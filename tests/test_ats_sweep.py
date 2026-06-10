"""Tests for ats_sweep.py — all HTTP mocked, no network access."""
from unittest.mock import patch, MagicMock

import pytest

from ats_sweep import ATSSweeper, clean_result_title, extract_org_name


SWEEP_CONFIG = {
    'date_restrict': 'd2',
    'results_per_query': 10,
    'max_api_calls': 90,
    'queries': {
        'Policy': ['Foreign Policy', 'Public Policy'],
    },
    'platforms': [
        {'name': 'Greenhouse', 'site': 'greenhouse.io'},
        {'name': 'SmartRecruiters', 'site': 'jobs.smartrecruiters.com',
         'exclude': ["Domino's"]},
    ],
}


def make_sweeper(**overrides):
    cfg = {**SWEEP_CONFIG, **overrides}
    return ATSSweeper('test-key', 'test-cx', cfg)


def api_response(items):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {'items': items}
    return resp


class TestOrgExtraction:
    @pytest.mark.parametrize("url,expected", [
        ("https://job-boards.greenhouse.io/givewell/jobs/5015528008", "Givewell"),
        ("https://boards.greenhouse.io/protect-democracy/jobs/123", "Protect Democracy"),
        ("https://jobs.lever.co/freedomhouse/abc-def", "Freedomhouse"),
        ("https://jobs.ashbyhq.com/open-philanthropy/role-id", "Open Philanthropy"),
        ("https://apply.workable.com/ned/j/ABC123/", "Ned"),
        ("https://jobs.smartrecruiters.com/GermanMarshallFund/123-program-officer",
         "Germanmarshallfund"),
        ("https://brookings.wd1.myworkdayjobs.com/Careers/job/123", "Brookings"),
        ("https://careers-cfr.icims.com/jobs/1234/program-officer/job", "Cfr"),
        ("https://www.governmentjobs.com/careers/lacity/jobs/456", "Lacity"),
        ("https://www.indeed.com/viewjob?jk=abc123", None),
    ])
    def test_extracts_org(self, url, expected):
        assert extract_org_name(url) == expected


class TestTitleCleaning:
    @pytest.mark.parametrize("raw,cleaned", [
        ("Director, Foreign Policy - Greenhouse", "Director, Foreign Policy"),
        ("Job Application for Program Officer at GiveWell", "Program Officer"),
        ("Senior Policy Analyst | SmartRecruiters", "Senior Policy Analyst"),
        ("Government Affairs Lead - Acme Careers - Lever", "Government Affairs Lead"),
        ("Program Officer", "Program Officer"),
    ])
    def test_strips_vendor_noise(self, raw, cleaned):
        assert clean_result_title(raw) == cleaned


class TestQueryBuilding:
    def test_query_includes_site_and_terms(self):
        sweeper = make_sweeper()
        q = sweeper._build_query('greenhouse.io', ['Foreign Policy', 'Public Policy'])
        assert q == 'site:greenhouse.io ("Foreign Policy" OR "Public Policy")'

    def test_exclusions_appended(self):
        sweeper = make_sweeper()
        q = sweeper._build_query('jobs.smartrecruiters.com', ['Policy'],
                                 exclude=["Domino's"])
        assert q.endswith('-"Domino\'s"')


class TestSweep:
    @patch('ats_sweep.requests.get')
    def test_sweep_maps_results_to_jobs(self, mock_get):
        mock_get.return_value = api_response([{
            'title': 'Program Officer - Greenhouse',
            'link': 'https://job-boards.greenhouse.io/givewell/jobs/123',
            'snippet': 'Lead our policy research grants program.',
        }])
        sweeper = make_sweeper()
        jobs = sweeper.sweep()

        # 2 platforms x 1 query, same result deduped by URL
        assert mock_get.call_count == 2
        assert len(jobs) == 1
        job = jobs[0]
        assert job['title'] == 'Program Officer'
        assert job['site_name'] == 'Givewell (Greenhouse)'
        assert job['keywords'] == 'Policy'
        assert job['description'].startswith('Lead our policy')

    @patch('ats_sweep.requests.get')
    def test_sweep_passes_date_restrict(self, mock_get):
        mock_get.return_value = api_response([])
        make_sweeper().sweep()
        params = mock_get.call_args[1]['params']
        assert params['dateRestrict'] == 'd2'
        assert params['key'] == 'test-key'
        assert params['cx'] == 'test-cx'

    @patch('ats_sweep.requests.get')
    def test_budget_cap_stops_sweep(self, mock_get):
        mock_get.return_value = api_response([])
        sweeper = make_sweeper(max_api_calls=1)
        sweeper.sweep()
        assert mock_get.call_count == 1

    @patch('ats_sweep.requests.get')
    def test_quota_429_stops_sweep(self, mock_get):
        mock_get.return_value = MagicMock(status_code=429)
        sweeper = make_sweeper()
        jobs = sweeper.sweep()
        assert jobs == []
        assert mock_get.call_count == 1

    @patch('ats_sweep.requests.get')
    def test_request_error_continues(self, mock_get):
        import requests as _requests
        mock_get.side_effect = _requests.ConnectionError("boom")
        jobs = make_sweeper().sweep()
        assert jobs == []
        assert mock_get.call_count == 2  # error on one query doesn't abort the rest

    @patch('ats_sweep.requests.get')
    def test_results_without_link_or_title_skipped(self, mock_get):
        mock_get.return_value = api_response([
            {'title': 'No link here', 'snippet': 'x'},
            {'link': 'https://example.org/jobs/1', 'title': '', 'snippet': 'x'},
        ])
        assert make_sweeper().sweep() == []
