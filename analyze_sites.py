#!/usr/bin/env python3
"""Analyze site performance in the job database"""

import sqlite3
import csv
from collections import defaultdict

def analyze_database():
    # Get all active sites from sites.csv
    active_sites = set()
    with open('sites.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('active', '').lower() in ['yes', 'true', '1']:
                active_sites.add(row['site_name'])

    print(f"Total active sites in sites.csv: {len(active_sites)}\n")

    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()

        # Get job counts by site
        cursor.execute("""
            SELECT site_name, COUNT(*) as job_count
            FROM jobs
            GROUP BY site_name
            ORDER BY job_count DESC
        """)

        site_jobs = dict(cursor.fetchall())
        sites_with_jobs = set(site_jobs.keys())

        print(f"Sites with jobs in database: {len(sites_with_jobs)}/{len(active_sites)}\n")

        # Sites with NO jobs
        sites_no_jobs = active_sites - sites_with_jobs
        print(f"Sites with NO jobs ({len(sites_no_jobs)}):")
        for site in sorted(sites_no_jobs):
            print(f"   - {site}")

        print(f"\nTop 20 sites by job count:")
        for site, count in sorted(site_jobs.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"   {count:4d} - {site}")

        # Check data quality - sites with missing descriptions
        cursor.execute("""
            SELECT site_name,
                   COUNT(*) as total_jobs,
                   SUM(CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END) as no_desc,
                   SUM(CASE WHEN location IS NULL OR location = '' THEN 1 ELSE 0 END) as no_location
            FROM jobs
            GROUP BY site_name
            HAVING total_jobs > 0
            ORDER BY (no_desc * 1.0 / total_jobs) DESC
        """)

        quality_issues = cursor.fetchall()

        print(f"\nSites with data quality issues (missing descriptions):")
        print(f"{'Site':<40} {'Total':>6} {'No Desc':>8} {'%':>6} {'No Loc':>7}")
        print("-" * 75)

        for site, total, no_desc, no_loc in quality_issues[:20]:
            if no_desc > 0:
                pct = (no_desc / total) * 100
                print(f"{site:<40} {total:6d} {no_desc:8d} {pct:5.1f}% {no_loc:7d}")

        # Check for sites with custom parsers
        cursor.execute("SELECT site_name FROM site_parsers")
        parsers = [row[0] for row in cursor.fetchall()]

        print(f"\nSites with custom parsers ({len(parsers)}):")
        for site in parsers:
            job_count = site_jobs.get(site, 0)
            print(f"   - {site} ({job_count} jobs)")

        # Recent activity check
        cursor.execute("""
            SELECT site_name, MAX(discovered_date) as last_discovery
            FROM jobs
            GROUP BY site_name
            ORDER BY last_discovery DESC
            LIMIT 10
        """)

        print(f"\nMost recently active sites:")
        for site, last_date in cursor.fetchall():
            print(f"   - {site}: {last_date}")

if __name__ == "__main__":
    analyze_database()
