#!/usr/bin/env python3
"""
Helper script to check for duplicates between new suggestions and rejected/existing sites
"""

import csv
import re
from typing import Set, List, Tuple


def load_existing_sites(sites_file: str = 'sites.csv') -> Set[str]:
    """Load all site names from the active sites CSV"""
    sites = set()
    try:
        with open(sites_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('site_name', '').strip().lower()
                if name:
                    sites.add(name)
    except FileNotFoundError:
        pass
    return sites


def load_rejected_sites(rejected_file: str = 'rejected_sites.txt') -> Set[str]:
    """Load all site names from the rejected sites file"""
    sites = set()
    try:
        with open(rejected_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and headers
                if line.startswith('#') or not line or line.startswith('=='):
                    continue
                # Extract site name (everything before the first ' - ')
                if ' - ' in line:
                    name = line.split(' - ')[0].strip().lower()
                    sites.add(name)
    except FileNotFoundError:
        pass
    return sites


def normalize_name(name: str) -> str:
    """Normalize a foundation name for comparison"""
    name = name.lower().strip()
    # Remove common suffixes
    name = re.sub(r'\s+(foundation|fund|institute|inc|llc|trust|philanthropies|ventures|collective|network|group|initiative|project)s?$', '', name)
    # Remove "the" prefix
    name = re.sub(r'^the\s+', '', name)
    return name


def check_duplicates(new_suggestions: List[Tuple[str, str]]) -> List[Tuple[str, str, str]]:
    """
    Check if new suggestions are duplicates

    Args:
        new_suggestions: List of (name, url) tuples

    Returns:
        List of (name, url, status) tuples where status is:
        - 'new' if not found anywhere
        - 'active' if already in sites.csv
        - 'rejected' if in rejected_sites.txt
    """
    existing = load_existing_sites()
    rejected = load_rejected_sites()

    # Pre-compute normalized sets for O(1) lookup
    existing_normalized = {normalize_name(name) for name in existing}
    rejected_normalized = {normalize_name(name) for name in rejected}

    results = []
    for name, url in new_suggestions:
        normalized = normalize_name(name)

        if name.lower() in existing or normalized in existing_normalized:
            status = 'active'
        elif name.lower() in rejected or normalized in rejected_normalized:
            status = 'rejected'
        else:
            status = 'new'

        results.append((name, url, status))

    return results


def validate_sites_csv(sites_file: str = 'sites.csv', rejected_file: str = 'rejected_sites.txt') -> Tuple[bool, List[str]]:
    """
    Validate that no active sites in sites.csv are in the rejected list

    Args:
        sites_file: Path to the sites.csv file
        rejected_file: Path to the rejected_sites.txt file

    Returns:
        Tuple of (is_valid, list_of_violations)
        - is_valid: True if no violations found, False otherwise
        - list_of_violations: List of site names that are both active and rejected
    """
    existing = load_existing_sites(sites_file)
    rejected = load_rejected_sites(rejected_file)

    violations = []

    # Read sites.csv to get full details
    try:
        with open(sites_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                site_name = row.get('site_name', '').strip()
                is_active = row.get('active', '').lower() in ['yes', 'true', '1']

                if not is_active:
                    continue

                # Check if active site is in rejected list
                normalized = normalize_name(site_name)

                # Check exact match
                if site_name.lower() in rejected:
                    violations.append(f"{site_name} (exact match in rejected list)")
                    continue

                # Check normalized match
                for rejected_name in rejected:
                    if normalize_name(rejected_name) == normalized:
                        violations.append(f"{site_name} (matches rejected: {rejected_name})")
                        break

    except FileNotFoundError:
        return False, [f"File not found: {sites_file}"]

    return len(violations) == 0, violations


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Check organizations against active/rejected lists'
    )
    parser.add_argument('names', nargs='*', help='Organization names to check')
    parser.add_argument('--validate', action='store_true',
                        help='Validate sites.csv against rejected list')
    parser.add_argument('--file', type=str,
                        help='Read organization names from file (one per line)')
    parser.add_argument('--new-only', action='store_true',
                        help='Only show NEW organizations')

    args = parser.parse_args()

    if args.validate:
        is_valid, violations = validate_sites_csv()

        if is_valid:
            print("✅ VALIDATION PASSED: No active sites found in rejected list")
            return 0
        else:
            print("❌ VALIDATION FAILED: Found active sites in rejected list:")
            print("="*80)
            for violation in violations:
                print(f"  ❌ {violation}")
            print("="*80)
            print(f"\nTotal violations: {len(violations)}")
            print("\nPlease remove these sites from sites.csv or mark them as inactive.")
            return 1

    suggestions = []

    if args.file:
        try:
            with open(args.file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if ' - ' in line:
                            name, url = line.split(' - ', 1)
                            suggestions.append((name.strip(), url.strip()))
                        else:
                            suggestions.append((line, ''))
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found")
            return 1
    else:
        for name in args.names:
            suggestions.append((name, ''))

    if not suggestions:
        parser.print_help()
        return

    results = check_duplicates(suggestions)

    new_count = sum(1 for _, _, status in results if status == 'new')
    active_count = sum(1 for _, _, status in results if status == 'active')
    rejected_count = sum(1 for _, _, status in results if status == 'rejected')

    display_results = results
    if args.new_only:
        display_results = [(name, url, status) for name, url, status in results if status == 'new']

    print("\nDuplicate Check Results:")
    print("="*80)

    for name, url, status in display_results:
        symbol = {'new': '✅', 'active': '🔵', 'rejected': '❌'}.get(status, '?')
        status_text = {
            'new': 'NEW - Safe to suggest',
            'active': 'ALREADY ACTIVE',
            'rejected': 'ALREADY REJECTED'
        }.get(status, 'UNKNOWN')

        print(f"{symbol} {name}")
        print(f"   Status: {status_text}")

    print("\n" + "="*80)
    if args.new_only:
        print(f"Showing: {new_count} new organizations")
        print(f"Filtered out: {active_count} already active, {rejected_count} already rejected")
    else:
        print(f"Summary: {new_count} new, {active_count} already active, {rejected_count} already rejected")
    print("="*80 + "\n")


if __name__ == "__main__":
    import sys
    exit_code = main()
    if exit_code is not None:
        sys.exit(exit_code)
