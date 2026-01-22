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

    results = []
    for name, url in new_suggestions:
        normalized = normalize_name(name)
        status = 'new'

        # Check exact match first
        if name.lower() in existing:
            status = 'active'
        elif name.lower() in rejected:
            status = 'rejected'
        else:
            # Check normalized name
            for existing_name in existing:
                if normalize_name(existing_name) == normalized:
                    status = 'active'
                    break

            if status == 'new':
                for rejected_name in rejected:
                    if normalize_name(rejected_name) == normalized:
                        status = 'rejected'
                        break

        results.append((name, url, status))

    return results


def main():
    """Example usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python check_duplicates.py 'Foundation Name' [url]")
        print("\nOr provide multiple foundations:")
        print("  python check_duplicates.py 'Foundation 1' 'Foundation 2' ...")
        return

    # Parse arguments as foundation names
    suggestions = []
    for arg in sys.argv[1:]:
        if arg.startswith('http'):
            continue  # Skip URLs
        suggestions.append((arg, ''))

    if not suggestions:
        print("No foundation names provided")
        return

    results = check_duplicates(suggestions)

    print("\nDuplicate Check Results:")
    print("="*80)

    new_count = 0
    active_count = 0
    rejected_count = 0

    for name, url, status in results:
        symbol = {
            'new': '✅',
            'active': '🔵',
            'rejected': '❌'
        }.get(status, '?')

        status_text = {
            'new': 'NEW - Safe to suggest',
            'active': 'ALREADY ACTIVE',
            'rejected': 'ALREADY REJECTED'
        }.get(status, 'UNKNOWN')

        print(f"{symbol} {name}")
        print(f"   Status: {status_text}")

        if status == 'new':
            new_count += 1
        elif status == 'active':
            active_count += 1
        elif status == 'rejected':
            rejected_count += 1

    print("\n" + "="*80)
    print(f"Summary: {new_count} new, {active_count} already active, {rejected_count} already rejected")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
