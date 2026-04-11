"""Tests for manage_sites.py"""
import csv
import os
import textwrap

import pytest

# We need to run manage_sites from the directory where the CSV files live,
# so we monkeypatch the file paths for isolation.
import manage_sites


@pytest.fixture
def site_env(tmp_path, monkeypatch):
    """Set up isolated CSV files for each test."""
    sites_csv = tmp_path / "sites.csv"
    rejected_txt = tmp_path / "rejected_sites.txt"
    candidates_csv = tmp_path / "candidates.csv"

    # Create sites.csv with one existing site
    sites_csv.write_text("site_name,url,active,keywords,scrape_details\n"
                         "Test Foundation,https://test.org/careers,yes,,no\n")

    # Create rejected_sites.txt with one rejected site
    rejected_txt.write_text("## Test Category\n"
                            "Rejected Org - https://rejected.org/careers\n")

    # Create empty candidates.csv
    candidates_csv.write_text("id,name,url,category,ats_type,job_count,date_added,status\n")

    # Monkeypatch file paths
    monkeypatch.setattr(manage_sites, 'SITES_FILE', str(sites_csv))
    monkeypatch.setattr(manage_sites, 'REJECTED_FILE', str(rejected_txt))
    monkeypatch.setattr(manage_sites, 'CANDIDATES_FILE', str(candidates_csv))

    return {
        'sites_csv': sites_csv,
        'rejected_txt': rejected_txt,
        'candidates_csv': candidates_csv,
        'tmp_path': tmp_path,
    }


class TestDuplicateChecking:
    def test_new_org_passes(self, site_env):
        result = manage_sites.check_duplicate("New Org", "https://new.org/careers")
        assert result is None

    def test_existing_name_caught(self, site_env):
        result = manage_sites.check_duplicate("Test Foundation", "https://different.org/careers")
        assert result is not None
        assert "active" in result

    def test_existing_name_normalized(self, site_env):
        # "Test" should match "Test Foundation" after normalization
        result = manage_sites.check_duplicate("The Test Foundation", "https://different.org/careers")
        assert result is not None
        assert "active" in result

    def test_existing_url_caught(self, site_env):
        result = manage_sites.check_duplicate("Different Name", "https://test.org/careers")
        assert result is not None
        assert "active" in result

    def test_rejected_name_caught(self, site_env):
        result = manage_sites.check_duplicate("Rejected Org", "https://different.org/careers")
        assert result is not None
        assert "rejected" in result

    def test_rejected_url_caught(self, site_env):
        result = manage_sites.check_duplicate("Different Name", "https://rejected.org/careers")
        assert result is not None
        assert "rejected" in result

    def test_candidate_url_caught(self, site_env):
        # Add a candidate first
        manage_sites.cmd_add_candidate(["Staged Org", "https://staged.org/careers"])
        result = manage_sites.check_duplicate("Other Name", "https://staged.org/careers")
        assert result is not None
        assert "candidates" in result


class TestAddCandidate:
    def test_add_single(self, site_env):
        ret = manage_sites.cmd_add_candidate(["New Org", "https://new.org/careers"])
        assert ret == 0

        candidates = manage_sites._read_candidates()
        assert len(candidates) == 1
        assert candidates[0]['name'] == "New Org"
        assert candidates[0]['url'] == "https://new.org/careers"
        assert candidates[0]['status'] == "pending"

    def test_add_with_category(self, site_env):
        ret = manage_sites.cmd_add_candidate([
            "New Org", "https://new.org/careers", "--category", "Democracy"
        ])
        assert ret == 0
        candidates = manage_sites._read_candidates()
        assert candidates[0]['category'] == "Democracy"

    def test_add_duplicate_blocked(self, site_env):
        ret = manage_sites.cmd_add_candidate(["Test Foundation", "https://whatever.org/careers"])
        assert ret == 1  # Should fail

        candidates = manage_sites._read_candidates()
        assert len(candidates) == 0

    def test_sequential_ids(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers"])
        manage_sites.cmd_add_candidate(["Org C", "https://c.org/careers"])

        candidates = manage_sites._read_candidates()
        ids = [int(c['id']) for c in candidates]
        assert ids == [1, 2, 3]


class TestAddBatch:
    def test_batch_add(self, site_env):
        batch_file = site_env['tmp_path'] / "batch.txt"
        batch_file.write_text("Org A - https://a.org/careers\n"
                              "Org B - https://b.org/careers\n"
                              "# comment line\n"
                              "Org C - https://c.org/careers\n")

        ret = manage_sites.cmd_add_batch([str(batch_file)])
        assert ret == 0

        candidates = manage_sites._read_candidates()
        assert len(candidates) == 3

    def test_batch_skips_duplicates(self, site_env):
        batch_file = site_env['tmp_path'] / "batch.txt"
        batch_file.write_text("Test Foundation - https://test.org/careers\n"
                              "New Org - https://new.org/careers\n")

        ret = manage_sites.cmd_add_batch([str(batch_file)])
        assert ret == 0

        candidates = manage_sites._read_candidates()
        assert len(candidates) == 1
        assert candidates[0]['name'] == "New Org"

    def test_batch_with_category(self, site_env):
        batch_file = site_env['tmp_path'] / "batch.txt"
        batch_file.write_text("Org A - https://a.org/careers\n")

        manage_sites.cmd_add_batch([str(batch_file), "--category", "Climate"])
        candidates = manage_sites._read_candidates()
        assert candidates[0]['category'] == "Climate"


class TestReview:
    def test_review_generates_file(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers", "--category", "Democracy"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers", "--category", "Climate"])

        output_file = str(site_env['tmp_path'] / "review.md")
        ret = manage_sites.cmd_review(["--output", output_file])
        assert ret == 0
        assert os.path.exists(output_file)

        content = open(output_file).read()
        assert "[ ]" in content
        assert "Org A" in content
        assert "Org B" in content
        assert "Democracy" in content
        assert "Climate" in content

    def test_review_empty_when_no_pending(self, site_env):
        ret = manage_sites.cmd_review([])
        assert ret == 0  # No error, just nothing to do

    def test_review_batch_limit(self, site_env):
        for i in range(10):
            manage_sites.cmd_add_candidate([f"Org {i}", f"https://org{i}.org/careers"])

        output_file = str(site_env['tmp_path'] / "review.md")
        manage_sites.cmd_review(["--batch", "3", "--output", output_file])

        content = open(output_file).read()
        # Should only have 3 checkboxes
        checkbox_count = content.count("- [ ]")
        assert checkbox_count == 3

    def test_review_default_batch_size(self, site_env):
        """Without --batch flag, should use DEFAULT_BATCH_SIZE."""
        for i in range(15):
            manage_sites.cmd_add_candidate([f"Org {i}", f"https://org{i}.org/careers"])

        output_file = str(site_env['tmp_path'] / "review.md")
        manage_sites.cmd_review(["--output", output_file])

        content = open(output_file).read()
        checkbox_count = content.count("- [ ]")
        assert checkbox_count == manage_sites.DEFAULT_BATCH_SIZE

    def test_review_start_flag(self, site_env):
        """--start ID filters to candidates at or after that ID."""
        for i in range(10):
            manage_sites.cmd_add_candidate([f"Org {i}", f"https://org{i}.org/careers"])

        output_file = str(site_env['tmp_path'] / "review.md")
        # IDs are 1-10; --start 6 should show IDs 6-10 (5 candidates)
        manage_sites.cmd_review(["--start", "6", "--batch", "20", "--output", output_file])

        content = open(output_file).read()
        checkbox_count = content.count("- [ ]")
        assert checkbox_count == 5
        assert "Org 0" not in content
        assert "Org 5" in content  # ID 6 = Org 5 (0-indexed names, 1-indexed IDs)

    def test_review_start_and_batch_combined(self, site_env):
        """--start and --batch work together."""
        for i in range(10):
            manage_sites.cmd_add_candidate([f"Org {i}", f"https://org{i}.org/careers"])

        output_file = str(site_env['tmp_path'] / "review.md")
        manage_sites.cmd_review(["--start", "3", "--batch", "2", "--output", output_file])

        content = open(output_file).read()
        checkbox_count = content.count("- [ ]")
        assert checkbox_count == 2


class TestDedupCache:
    def test_cache_detects_existing(self, site_env):
        cache = manage_sites._DedupCache()
        assert cache.check("Test Foundation", "https://whatever.org") is not None
        assert "active" in cache.check("Test Foundation", "https://whatever.org")

    def test_cache_detects_rejected(self, site_env):
        cache = manage_sites._DedupCache()
        assert cache.check("Rejected Org", "https://whatever.org") is not None
        assert "rejected" in cache.check("Rejected Org", "https://whatever.org")

    def test_cache_allows_new(self, site_env):
        cache = manage_sites._DedupCache()
        assert cache.check("Brand New Org", "https://brandnew.org/careers") is None

    def test_cache_register_prevents_duplicates(self, site_env):
        cache = manage_sites._DedupCache()
        assert cache.check("New Org", "https://new.org/careers") is None
        cache.register("New Org", "https://new.org/careers")
        assert cache.check("New Org", "https://other.org") is not None
        assert cache.check("Other Name", "https://new.org/careers") is not None

    def test_no_false_positive_on_same_domain_different_path(self, site_env):
        """Different paths on the same domain should NOT be flagged as duplicates."""
        cache = manage_sites._DedupCache()
        # test.org/careers is in sites.csv, but test.org/jobs is a different URL
        result = cache.check("Different Org", "https://test.org/jobs")
        assert result is None


class TestProcess:
    def test_process_approvals(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers"])

        # Create a review file with Org A checked
        review_file = site_env['tmp_path'] / "review.md"
        review_file.write_text(
            "# Review\n\n"
            "- [x] **1. Org A** — https://a.org/careers\n"
            "  0 jobs\n\n"
            "- [ ] **2. Org B** — https://b.org/careers\n"
            "  0 jobs\n"
        )

        ret = manage_sites.cmd_process([str(review_file)])
        assert ret == 0

        # Org A should be in sites.csv
        sites_content = site_env['sites_csv'].read_text()
        assert "Org A" in sites_content

        # Org B should be in rejected
        rejected_content = site_env['rejected_txt'].read_text()
        assert "Org B" in rejected_content

        # Candidate statuses should be updated
        candidates = manage_sites._read_candidates()
        statuses = {c['name']: c['status'] for c in candidates}
        assert statuses['Org A'] == 'approved'
        assert statuses['Org B'] == 'rejected'

        # Review file should be cleaned up
        assert not review_file.exists()

    def test_process_sites_csv_format(self, site_env):
        """Verify appended rows use correct CSV format."""
        manage_sites.cmd_add_candidate(["Org With Comma, Inc", "https://comma.org/careers"])

        review_file = site_env['tmp_path'] / "review.md"
        review_file.write_text(
            '- [x] **1. Org With Comma, Inc** — https://comma.org/careers\n'
        )

        manage_sites.cmd_process([str(review_file)])

        # Read back with csv module to verify proper quoting
        with open(site_env['sites_csv'], 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        names = [r['site_name'] for r in rows]
        assert "Org With Comma, Inc" in names

        # Review file should be cleaned up
        assert not review_file.exists()


class TestQuickApproveReject:
    def test_approve_by_id(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers"])

        manage_sites.cmd_approve(["1"])

        candidates = manage_sites._read_candidates()
        statuses = {c['name']: c['status'] for c in candidates}
        assert statuses['Org A'] == 'approved'
        assert statuses['Org B'] == 'pending'

        # Should be in sites.csv
        sites_content = site_env['sites_csv'].read_text()
        assert "Org A" in sites_content

    def test_reject_by_id(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])

        manage_sites.cmd_reject(["1"])

        candidates = manage_sites._read_candidates()
        assert candidates[0]['status'] == 'rejected'

        rejected_content = site_env['rejected_txt'].read_text()
        assert "Org A" in rejected_content

    def test_double_approve_skipped(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_approve(["1"])
        manage_sites.cmd_approve(["1"])  # Should be a no-op

        # Should only appear once in sites.csv
        sites_content = site_env['sites_csv'].read_text()
        assert sites_content.count("Org A") == 1


class TestStatus:
    def test_status_counts(self, site_env, capsys):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers"])
        manage_sites.cmd_approve(["1"])

        manage_sites.cmd_status([])
        output = capsys.readouterr().out
        assert "pending: 1" in output
        assert "approved: 1" in output


class TestClearProcessed:
    def test_clear_removes_non_pending(self, site_env):
        manage_sites.cmd_add_candidate(["Org A", "https://a.org/careers"])
        manage_sites.cmd_add_candidate(["Org B", "https://b.org/careers"])
        manage_sites.cmd_add_candidate(["Org C", "https://c.org/careers"])
        manage_sites.cmd_approve(["1"])
        manage_sites.cmd_reject(["2"])

        manage_sites.cmd_clear_processed([])

        candidates = manage_sites._read_candidates()
        assert len(candidates) == 1
        assert candidates[0]['name'] == "Org C"


class TestRemoveSite:
    def test_remove_existing_site(self, site_env):
        ret = manage_sites.cmd_remove(["Test Foundation"])
        assert ret == 0
        with open(site_env['sites_csv']) as f:
            content = f.read()
        assert "Test Foundation" not in content
        rejected = site_env['rejected_txt'].read_text()
        assert "Test Foundation" in rejected
        assert "https://test.org/careers" in rejected

    def test_remove_case_insensitive(self, site_env):
        ret = manage_sites.cmd_remove(["test foundation"])
        assert ret == 0
        with open(site_env['sites_csv']) as f:
            content = f.read()
        assert "Test Foundation" not in content

    def test_remove_nonexistent_fails(self, site_env):
        ret = manage_sites.cmd_remove(["Nonexistent Org"])
        assert ret == 1
        # sites.csv should be untouched
        with open(site_env['sites_csv']) as f:
            content = f.read()
        assert "Test Foundation" in content

    def test_remove_no_reject_skips_rejected_file(self, site_env):
        original_rejected = site_env['rejected_txt'].read_text()
        ret = manage_sites.cmd_remove(["Test Foundation", "--no-reject"])
        assert ret == 0
        with open(site_env['sites_csv']) as f:
            content = f.read()
        assert "Test Foundation" not in content
        assert site_env['rejected_txt'].read_text() == original_rejected

    def test_remove_preserves_other_sites(self, site_env):
        # Add a second site
        with open(site_env['sites_csv'], 'a') as f:
            f.write("Other Org,https://other.org/jobs,yes,,no\n")
        ret = manage_sites.cmd_remove(["Test Foundation"])
        assert ret == 0
        with open(site_env['sites_csv']) as f:
            content = f.read()
        assert "Test Foundation" not in content
        assert "Other Org" in content
        assert "https://other.org/jobs" in content


class TestURLDedup:
    """Test that URL-based dedup works in check_duplicates.py too."""

    def test_url_loading(self, tmp_path):
        """Test check_duplicates URL loading functions."""
        import check_duplicates as cd

        sites_csv = tmp_path / "sites.csv"
        rejected_txt = tmp_path / "rejected_sites.txt"

        sites_csv.write_text("site_name,url,active,keywords,scrape_details\n"
                             "Test Org,https://test.org/careers,yes,,no\n")
        rejected_txt.write_text("Rejected Org - https://rejected.org/careers\n")

        existing_urls = cd.load_existing_urls(str(sites_csv))
        rejected_urls = cd.load_rejected_urls(str(rejected_txt))

        # Verify full URL loading works (no bare domains)
        assert 'https://test.org/careers' in existing_urls
        assert 'test.org' not in existing_urls  # bare domains no longer stored
        assert 'https://rejected.org/careers' in rejected_urls
        assert 'rejected.org' not in rejected_urls  # bare domains no longer stored
