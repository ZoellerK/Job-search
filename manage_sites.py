#!/usr/bin/env python3
"""
Site management pipeline — discovery, staging, review, and approval.

Replaces manual CSV editing with a structured workflow:
  1. Candidates go into candidates.csv (staging area)
  2. Review generates a checkbox markdown file
  3. Processing moves approved → sites.csv, rejected → rejected_sites.txt
"""

import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from check_duplicates import load_existing_sites, load_rejected_sites, normalize_name

CANDIDATES_FILE = 'candidates.csv'
SITES_FILE = 'sites.csv'
REJECTED_FILE = 'rejected_sites.txt'
DEFAULT_BATCH_SIZE = 10
CANDIDATES_FIELDS = [
    'id', 'name', 'url', 'category', 'description', 'ats_type', 'job_count',
    'date_added', 'status',  # pending | approved | rejected
]


# ── Helpers ──────────────────────────────────────────────────────────────

def _next_candidate_id() -> int:
    """Return the next available candidate ID."""
    max_id = 0
    for row in _read_candidates():
        try:
            max_id = max(max_id, int(row['id']))
        except (ValueError, KeyError):
            pass
    return max_id + 1


def _read_candidates() -> List[Dict]:
    """Read all candidates from the staging CSV."""
    if not os.path.exists(CANDIDATES_FILE):
        return []
    with open(CANDIDATES_FILE, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # Backfill missing 'description' field for old rows
    for row in rows:
        if 'description' not in row:
            row['description'] = ''
    return rows


def _write_candidates(rows: List[Dict]):
    """Write candidates back to the staging CSV."""
    with open(CANDIDATES_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATES_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _parse_url_key(url: str) -> str:
    """Normalize a URL for dedup: lowercase, strip trailing slash."""
    return url.lower().rstrip('/')


def _load_existing_urls(sites_file: str = None) -> Set[str]:
    """Load all full URLs from sites.csv (no bare domains)."""
    if sites_file is None:
        sites_file = SITES_FILE
    urls = set()
    try:
        with open(sites_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('url', '').strip()
                if url:
                    urls.add(_parse_url_key(url))
    except FileNotFoundError:
        pass
    return urls


def _load_rejected_urls(rejected_file: str = None) -> Set[str]:
    """Load all full URLs from rejected_sites.txt (no bare domains)."""
    if rejected_file is None:
        rejected_file = REJECTED_FILE
    urls = set()
    try:
        with open(rejected_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or line.startswith('##') or not line:
                    continue
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        url = parts[1].strip()
                        # Strip trailing notes like "(ADDED THEN REMOVED)"
                        url = re.sub(r'\s*\(.*?\)\s*$', '', url)
                        if url:
                            urls.add(_parse_url_key(url))
    except FileNotFoundError:
        pass
    return urls


class _DedupCache:
    """
    Preloads all name/URL data from sites.csv, rejected_sites.txt, and
    candidates.csv once, then answers duplicate checks in O(1).
    """

    def __init__(self):
        # Names
        existing_names = load_existing_sites(SITES_FILE)
        rejected_names = load_rejected_sites(REJECTED_FILE)
        self.existing_names_lower = existing_names  # already lowered
        self.rejected_names_lower = rejected_names
        self.existing_names_normalized = {normalize_name(n) for n in existing_names}
        self.rejected_names_normalized = {normalize_name(n) for n in rejected_names}

        # URLs (full URLs only — no bare domains)
        self.existing_urls = _load_existing_urls()
        self.rejected_urls = _load_rejected_urls()

        # Candidates
        candidates = _read_candidates()
        self.candidate_urls = set()
        self.candidate_names_normalized: Dict[str, str] = {}  # normalized -> original
        for row in candidates:
            curl = row.get('url', '').strip()
            if curl:
                self.candidate_urls.add(_parse_url_key(curl))
            cname = row.get('name', '')
            if cname:
                self.candidate_names_normalized[normalize_name(cname)] = cname

    def check(self, name: str, url: str) -> Optional[str]:
        """Return None if new, or a description of where found."""
        normalized = normalize_name(name)

        # Name checks
        if name.lower() in self.existing_names_lower or normalized in self.existing_names_normalized:
            return f"already active in {SITES_FILE} (name match)"
        if name.lower() in self.rejected_names_lower or normalized in self.rejected_names_normalized:
            return f"already rejected in {REJECTED_FILE} (name match)"

        # URL checks (exact full-URL match only)
        url_lower = _parse_url_key(url)
        if url_lower in self.existing_urls:
            return f"already active in {SITES_FILE} (URL match)"
        if url_lower in self.rejected_urls:
            return f"already rejected in {REJECTED_FILE} (URL match)"

        # Candidate checks
        if url_lower in self.candidate_urls:
            return f"already in {CANDIDATES_FILE} (URL match)"
        orig = self.candidate_names_normalized.get(normalized)
        if orig is not None:
            return f"already in {CANDIDATES_FILE} (name match: {orig})"

        return None

    def register(self, name: str, url: str):
        """Track a just-added candidate so subsequent checks see it."""
        self.candidate_urls.add(_parse_url_key(url))
        self.candidate_names_normalized[normalize_name(name)] = name


def check_duplicate(name: str, url: str) -> Optional[str]:
    """
    Check if a name/URL is already tracked anywhere.
    Returns None if new, or a string describing where it was found.
    Creates a fresh cache each call — for batch operations use _DedupCache directly.
    """
    return _DedupCache().check(name, url)


def test_url(url: str) -> Dict:
    """
    Test a URL: fetch it, detect ATS, count jobs.
    Returns dict with keys: reachable, ats_type, job_count, error
    """
    result = {'reachable': False, 'ats_type': None, 'job_count': 0, 'error': None}

    try:
        from scraper import JobScraper
        from ats_parsers import detect_ats, parse_ats_page
    except ImportError as e:
        result['error'] = f"Import error: {e}"
        return result

    ats = detect_ats(url)
    result['ats_type'] = ats

    try:
        scraper = JobScraper()
        soup = scraper.fetch_page(url)
        if not soup:
            result['error'] = "Could not fetch page"
            return result

        result['reachable'] = True

        if ats:
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            jobs = parse_ats_page(ats, soup, base)
            if jobs:
                result['job_count'] = len(jobs)
                return result

        # Fall back to auto-detect
        jobs = scraper.auto_detect_jobs(url)
        result['job_count'] = len(jobs) if jobs else 0

    except Exception as e:
        result['error'] = str(e)

    return result


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_add_candidate(args):
    """Add one or more candidates to the staging CSV."""
    if len(args) < 2:
        print("Usage: python manage_sites.py add <name> <url> [--category CAT] [--description DESC] [--test]")
        return 1

    name = args[0]
    url = args[1]
    category = ''
    description = ''
    do_test = False

    i = 2
    while i < len(args):
        if args[i] == '--category' and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        elif args[i] == '--description' and i + 1 < len(args):
            description = args[i + 1]
            i += 2
        elif args[i] == '--test':
            do_test = True
            i += 1
        else:
            i += 1

    # Dedup check
    dup = check_duplicate(name, url)
    if dup:
        print(f"SKIP: {name} — {dup}")
        return 1

    ats_type = ''
    job_count = 0

    if do_test:
        print(f"Testing {url}...")
        info = test_url(url)
        ats_type = info.get('ats_type') or ''
        job_count = info.get('job_count', 0)
        if info.get('error'):
            print(f"  Warning: {info['error']}")
        else:
            print(f"  Reachable: {info['reachable']}")
            print(f"  ATS: {ats_type or 'none detected'}")
            print(f"  Jobs found: {job_count}")
    else:
        # Quick ATS detection without fetching
        try:
            from ats_parsers import detect_ats
            ats_type = detect_ats(url) or ''
        except ImportError:
            pass

    candidate_id = _next_candidate_id()
    row = {
        'id': str(candidate_id),
        'name': name,
        'url': url,
        'category': category,
        'description': description,
        'ats_type': ats_type,
        'job_count': str(job_count),
        'date_added': datetime.now().strftime('%Y-%m-%d'),
        'status': 'pending',
    }

    candidates = _read_candidates()
    candidates.append(row)
    _write_candidates(candidates)

    print(f"Added candidate #{candidate_id}: {name}")
    return 0


def cmd_add_batch(args):
    """
    Add multiple candidates from a file.
    File format: one per line, 'Name - URL - Description' or 'Name,URL,Description'
    Description is optional. --category CAT applies to all entries.
    """
    if len(args) < 1:
        print("Usage: python manage_sites.py add-batch <file> [--category CAT]")
        return 1

    filepath = args[0]
    category = ''
    i = 1
    while i < len(args):
        if args[i] == '--category' and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        else:
            i += 1

    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return 1

    entries = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ' - ' in line:
                parts = line.split(' - ')
                if len(parts) >= 3:
                    entries.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
                elif len(parts) == 2:
                    entries.append((parts[0].strip(), parts[1].strip(), ''))
            elif ',' in line:
                parts = line.split(',')
                desc = parts[2].strip() if len(parts) >= 3 else ''
                entries.append((parts[0].strip(), parts[1].strip(), desc))

    # Load once, check many
    cache = _DedupCache()
    candidates = _read_candidates()
    next_id = max((int(c['id']) for c in candidates if c.get('id', '').isdigit()), default=0) + 1

    added = 0
    skipped = 0
    for name, url, desc in entries:
        dup = cache.check(name, url)
        if dup:
            print(f"  SKIP: {name} — {dup}")
            skipped += 1
            continue

        ats_type = ''
        try:
            from ats_parsers import detect_ats
            ats_type = detect_ats(url) or ''
        except ImportError:
            pass

        row = {
            'id': str(next_id),
            'name': name,
            'url': url,
            'category': category,
            'description': desc,
            'ats_type': ats_type,
            'job_count': '0',
            'date_added': datetime.now().strftime('%Y-%m-%d'),
            'status': 'pending',
        }
        candidates.append(row)
        cache.register(name, url)
        next_id += 1
        added += 1

    # Single write at the end
    _write_candidates(candidates)

    print(f"\nAdded {added} candidates, skipped {skipped} duplicates.")
    return 0


def cmd_test(args):
    """Test a URL without adding it."""
    if len(args) < 1:
        print("Usage: python manage_sites.py test <url>")
        return 1

    url = args[0]
    name = args[1] if len(args) > 1 else ''

    print(f"\nTesting: {url}")
    print("=" * 60)

    # Dedup check
    if name:
        dup = check_duplicate(name, url)
    else:
        # Check URL only
        dup = None
        url_lower = _parse_url_key(url)
        if url_lower in _load_existing_urls():
            dup = f"URL already in {SITES_FILE}"
        elif url_lower in _load_rejected_urls():
            dup = f"URL already in {REJECTED_FILE}"

    if dup:
        print(f"Duplicate: {dup}")
    else:
        print("Duplicate check: CLEAR")

    info = test_url(url)
    print(f"Reachable:  {info['reachable']}")
    print(f"ATS:        {info['ats_type'] or 'none detected'}")
    print(f"Jobs found: {info['job_count']}")
    if info.get('error'):
        print(f"Error:      {info['error']}")

    return 0


def cmd_review(args):
    """Generate a review markdown file with checkboxes for pending candidates."""
    candidates = _read_candidates()
    pending = [c for c in candidates if c.get('status') == 'pending']

    if not pending:
        print("No pending candidates to review.")
        return 0

    # Parse flags
    batch_size = DEFAULT_BATCH_SIZE
    output_file = None
    start_id = None
    i = 0
    while i < len(args):
        if args[i] == '--batch' and i + 1 < len(args):
            batch_size = int(args[i + 1])
            i += 2
        elif args[i] == '--output' and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == '--start' and i + 1 < len(args):
            start_id = int(args[i + 1])
            i += 2
        else:
            i += 1

    # Filter to candidates at or after --start ID
    if start_id is not None:
        pending = [c for c in pending if int(c.get('id', 0)) >= start_id]

    pending = pending[:batch_size]

    if not output_file:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_file = f'review_{date_str}.md'

    # Group by category
    by_category = {}
    for c in pending:
        cat = c.get('category', '').strip() or 'Uncategorized'
        by_category.setdefault(cat, []).append(c)

    lines = []
    lines.append(f"# Candidate Review ({datetime.now().strftime('%Y-%m-%d')})")
    lines.append('')
    lines.append(f'{len(pending)} candidates to review. Check `[x]` to approve, leave `[ ]` to reject.')
    lines.append('')

    for cat, items in sorted(by_category.items()):
        lines.append(f'## {cat} ({len(items)})')
        lines.append('')
        for c in items:
            cid = c['id']
            name = c['name']
            url = c['url']
            ats = c.get('ats_type', '')
            jobs = c.get('job_count', '0')

            detail_parts = []
            if ats:
                detail_parts.append(ats.capitalize())
            detail_parts.append(f"{jobs} jobs")

            detail = ' | '.join(detail_parts)
            lines.append(f"- [ ] **{cid}. {name}** — {url}")
            lines.append(f"  {detail}")
            lines.append('')

    lines.append('---')
    lines.append('Run `python manage_sites.py process ' + output_file + '` after marking your choices.')

    with open(output_file, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Review file written: {output_file}")
    print(f"  {len(pending)} candidates across {len(by_category)} categories")
    print(f"\nEdit the file, check [x] the ones you want, then run:")
    print(f"  python manage_sites.py process {output_file}")
    return 0


def cmd_process(args):
    """Process a review markdown file — approved → sites.csv, unchecked → rejected."""
    if len(args) < 1:
        print("Usage: python manage_sites.py process <review_file.md>")
        return 1

    review_file = args[0]
    if not os.path.exists(review_file):
        print(f"Error: File not found: {review_file}")
        return 1

    # Parse the review file for checked/unchecked items
    approved_ids = set()
    rejected_ids = set()

    with open(review_file, 'r') as f:
        for line in f:
            line = line.rstrip()
            # Match checked: - [x] **ID. Name** — URL
            m = re.match(r'^- \[x\] \*\*(\d+)\.\s', line, re.IGNORECASE)
            if m:
                approved_ids.add(m.group(1))
                continue
            # Match unchecked: - [ ] **ID. Name** — URL
            m = re.match(r'^- \[ \] \*\*(\d+)\.\s', line)
            if m:
                rejected_ids.add(m.group(1))

    if not approved_ids and not rejected_ids:
        print("No checkboxes found in the review file. Nothing to process.")
        return 1

    candidates = _read_candidates()
    candidates_by_id = {c['id']: c for c in candidates}

    added_to_sites = []
    added_to_rejected = []

    # Process approved
    for cid in approved_ids:
        c = candidates_by_id.get(cid)
        if not c:
            print(f"  Warning: candidate #{cid} not found in {CANDIDATES_FILE}")
            continue
        _append_to_sites_csv(c['name'], c['url'])
        c['status'] = 'approved'
        added_to_sites.append(c['name'])

    # Process rejected
    for cid in rejected_ids:
        c = candidates_by_id.get(cid)
        if not c:
            continue
        _append_to_rejected(c['name'], c['url'])
        c['status'] = 'rejected'
        added_to_rejected.append(c['name'])

    # Write updated candidates
    _write_candidates(candidates)

    print(f"\nProcessed {len(approved_ids) + len(rejected_ids)} candidates:")
    print(f"  Approved (→ {SITES_FILE}): {len(added_to_sites)}")
    for name in added_to_sites:
        print(f"    + {name}")
    print(f"  Rejected (→ {REJECTED_FILE}): {len(added_to_rejected)}")
    for name in added_to_rejected:
        print(f"    - {name}")

    # Clean up review file — decisions are recorded in candidates.csv
    os.remove(review_file)
    print(f"\nCleaned up {review_file}")

    return 0


def _append_to_sites_csv(name: str, url: str, keywords: str = '', scrape_details: str = 'no'):
    """Safely append a row to sites.csv using csv.writer."""
    with open(SITES_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([name, url, 'yes', keywords, scrape_details])


def _append_to_rejected(name: str, url: str):
    """Append an entry to rejected_sites.txt."""
    with open(REJECTED_FILE, 'a') as f:
        f.write(f"{name} - {url}\n")


def cmd_approve(args):
    """Quick-approve candidates by ID (skip review file)."""
    if not args:
        print("Usage: python manage_sites.py approve <id> [id ...]")
        return 1

    candidates = _read_candidates()
    candidates_by_id = {c['id']: c for c in candidates}
    count = 0

    for cid in args:
        c = candidates_by_id.get(cid)
        if not c:
            print(f"  Warning: candidate #{cid} not found")
            continue
        if c['status'] != 'pending':
            print(f"  Skip #{cid} ({c['name']}): already {c['status']}")
            continue
        _append_to_sites_csv(c['name'], c['url'])
        c['status'] = 'approved'
        print(f"  Approved: {c['name']} → {SITES_FILE}")
        count += 1

    _write_candidates(candidates)
    print(f"\n{count} candidate(s) approved.")
    return 0


def cmd_reject(args):
    """Quick-reject candidates by ID (skip review file)."""
    if not args:
        print("Usage: python manage_sites.py reject <id> [id ...]")
        return 1

    candidates = _read_candidates()
    candidates_by_id = {c['id']: c for c in candidates}
    count = 0

    for cid in args:
        c = candidates_by_id.get(cid)
        if not c:
            print(f"  Warning: candidate #{cid} not found")
            continue
        if c['status'] != 'pending':
            print(f"  Skip #{cid} ({c['name']}): already {c['status']}")
            continue
        _append_to_rejected(c['name'], c['url'])
        c['status'] = 'rejected'
        print(f"  Rejected: {c['name']} → {REJECTED_FILE}")
        count += 1

    _write_candidates(candidates)
    print(f"\n{count} candidate(s) rejected.")
    return 0


def cmd_remove(args):
    """Remove a site from sites.csv and add it to rejected_sites.txt."""
    if not args:
        print("Usage: python manage_sites.py remove <name> [--no-reject]")
        return 1

    name = args[0]
    add_to_rejected = '--no-reject' not in args

    if not os.path.exists(SITES_FILE):
        print(f"Error: {SITES_FILE} not found")
        return 1

    with open(SITES_FILE, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    name_lower = name.lower()
    matches = [r for r in rows if r.get('site_name', '').lower() == name_lower]
    if not matches:
        print(f"Error: no site named '{name}' found in {SITES_FILE}")
        return 1
    if len(matches) > 1:
        print(f"Warning: {len(matches)} rows match '{name}' - removing all")

    kept = [r for r in rows if r.get('site_name', '').lower() != name_lower]

    with open(SITES_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(kept)

    if add_to_rejected:
        for m in matches:
            _append_to_rejected(m['site_name'], m.get('url', ''))

    print(f"Removed {len(matches)} row(s) for '{name}' from {SITES_FILE}")
    if add_to_rejected:
        print(f"Added to {REJECTED_FILE} to prevent re-addition")
    return 0


def cmd_status(args):
    """Show candidate counts by status."""
    candidates = _read_candidates()
    counts = Counter(c.get('status', 'unknown') for c in candidates)

    print(f"\nCandidates: {len(candidates)} total")
    for status in ['pending', 'approved', 'rejected']:
        print(f"  {status}: {counts.get(status, 0)}")

    if counts.get('pending', 0) > 0:
        print(f"\nRun 'python manage_sites.py review' to generate a review file.")
    return 0


def cmd_patterns(args):
    """Analyze approved sites to show patterns that guide future discovery."""
    # Load sites.csv
    sites = []
    try:
        with open(SITES_FILE, 'r') as f:
            reader = csv.DictReader(f)
            sites = list(reader)
    except FileNotFoundError:
        print(f"Error: {SITES_FILE} not found")
        return 1

    active = [s for s in sites if s.get('active', '').lower() in ('yes', 'true', '1')]
    print(f"\n{'='*60}")
    print(f"APPROVAL PATTERNS — {len(active)} active sites")
    print(f"{'='*60}")

    # ATS platform distribution
    ats_counts = Counter()
    non_ats = 0
    for s in active:
        url = s.get('url', '')
        try:
            from ats_parsers import detect_ats
            ats = detect_ats(url)
            if ats:
                ats_counts[ats] += 1
            else:
                non_ats += 1
        except ImportError:
            non_ats += 1

    print(f"\nATS Platforms:")
    for ats, count in ats_counts.most_common():
        pct = count / len(active) * 100
        bar = '#' * int(pct / 2)
        print(f"  {ats:15s} {count:3d} ({pct:4.1f}%) {bar}")
    print(f"  {'custom/other':15s} {non_ats:3d} ({non_ats/len(active)*100:4.1f}%)")

    # Domain patterns (what kinds of URLs)
    domain_patterns = Counter()
    for s in active:
        url = s.get('url', '')
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if 'idealist.org' in host:
            domain_patterns['idealist.org (aggregator)'] += 1
        elif 'greenhouse.io' in host:
            domain_patterns['greenhouse.io'] += 1
        elif 'lever.co' in host:
            domain_patterns['lever.co'] += 1
        elif 'workable.com' in host:
            domain_patterns['workable.com'] += 1
        elif 'teamtailor.com' in host:
            domain_patterns['teamtailor.com'] += 1
        elif 'icims.com' in host:
            domain_patterns['icims.com'] += 1
        elif 'myworkdayjobs.com' in host:
            domain_patterns['myworkdayjobs.com'] += 1
        elif 'applicantpro.com' in host:
            domain_patterns['applicantpro.com'] += 1
        else:
            domain_patterns['org-hosted careers page'] += 1

    print(f"\nURL Patterns:")
    for pattern, count in domain_patterns.most_common():
        print(f"  {pattern:30s} {count:3d}")

    # Name patterns — extract common words
    name_words = Counter()
    stop_words = {'the', 'for', 'of', 'and', 'in', 'a', 'an', 'inc', 'org'}
    for s in active:
        name = s.get('site_name', '').lower()
        words = re.findall(r'\b[a-z]+\b', name)
        for w in words:
            if w not in stop_words and len(w) > 2:
                name_words[w] += 1

    print(f"\nCommon Name Terms (top 15):")
    for word, count in name_words.most_common(15):
        if count >= 2:
            print(f"  {word:20s} {count}")

    # Keyword analysis
    keywords_used = Counter()
    for s in active:
        kw = s.get('keywords', '').strip()
        if kw:
            for k in kw.split(','):
                k = k.strip().lower()
                if k:
                    keywords_used[k] += 1

    if keywords_used:
        print(f"\nKeywords in use:")
        for kw, count in keywords_used.most_common(10):
            print(f"  {kw:20s} {count}")
    else:
        print(f"\nKeywords: none configured (all sites use broad matching)")

    # Summary insights
    print(f"\n{'='*60}")
    print("INSIGHTS FOR DISCOVERY:")
    print(f"{'='*60}")
    print(f"  - {len(active)} orgs approved vs ~{_count_rejected()} rejected ({_approval_rate(len(active))}% approval rate)")
    if ats_counts:
        top_ats = ats_counts.most_common(1)[0]
        print(f"  - Top ATS: {top_ats[0]} ({top_ats[1]} sites) — orgs on this platform are good candidates")
    print(f"  - Most sites use org-hosted career pages (direct URL scraping)")
    print(f"  - Focus on: foundations, democracy/governance, philanthropy orgs")
    print()
    return 0


def _count_rejected() -> int:
    """Count entries in rejected_sites.txt."""
    count = 0
    try:
        with open(REJECTED_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('##') and ' - ' in line:
                    count += 1
    except FileNotFoundError:
        pass
    return count


def _approval_rate(approved: int) -> str:
    rejected = _count_rejected()
    total = approved + rejected
    if total == 0:
        return '0'
    return f"{approved / total * 100:.0f}"


def cmd_clear_processed(args):
    """Remove approved/rejected candidates from the staging file."""
    candidates = _read_candidates()
    pending = [c for c in candidates if c.get('status') == 'pending']
    removed = len(candidates) - len(pending)
    _write_candidates(pending)
    print(f"Cleared {removed} processed candidates. {len(pending)} pending remain.")
    return 0


# ── Main ─────────────────────────────────────────────────────────────────

COMMANDS = {
    'add': cmd_add_candidate,
    'add-batch': cmd_add_batch,
    'test': cmd_test,
    'review': cmd_review,
    'process': cmd_process,
    'approve': cmd_approve,
    'reject': cmd_reject,
    'remove': cmd_remove,
    'status': cmd_status,
    'patterns': cmd_patterns,
    'clear': cmd_clear_processed,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print("Site Management Pipeline")
        print()
        print("Discovery & staging:")
        print("  add <name> <url> [--category CAT] [--description DESC] [--test]")
        print("      Add a candidate to the staging area")
        print("  add-batch <file> [--category CAT]")
        print("      Bulk-add candidates from a file (Name - URL - Description per line)")
        print("  test <url> [name]")
        print("      Test a URL (dedup + fetch + ATS detect + job count)")
        print()
        print("Review & approval:")
        print(f"  review [--batch N] [--start ID] [--output FILE]   (default batch: {DEFAULT_BATCH_SIZE})")
        print("      Generate a checkbox review file for pending candidates")
        print("  process <review_file.md>")
        print("      Process a review file (checked → sites.csv, unchecked → rejected, file deleted)")
        print("  approve <id> [id ...]")
        print("      Quick-approve candidates by ID number")
        print("  reject <id> [id ...]")
        print("      Quick-reject candidates by ID number")
        print("  remove <name> [--no-reject]")
        print("      Remove a site from sites.csv (adds to rejected_sites.txt unless --no-reject)")
        print()
        print("Analysis:")
        print("  status    Show candidate counts by status")
        print("  patterns  Analyze approved sites for discovery patterns")
        print("  clear     Remove processed candidates from staging")
        return 0

    cmd_name = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd_name not in COMMANDS:
        print(f"Unknown command: {cmd_name}")
        print("Run 'python manage_sites.py help' for usage.")
        return 1

    return COMMANDS[cmd_name](cmd_args)


if __name__ == '__main__':
    sys.exit(main() or 0)
