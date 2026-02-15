#!/usr/bin/env python3
"""Test multiple problematic sites to identify common issues"""

from scraper import JobScraper
from database import JobDatabase

def test_site(scraper, db, site_name, url):
    """Test a single site and return results"""
    print(f"\n{'='*70}")
    print(f"Testing: {site_name}")
    print(f"URL: {url}")
    print('='*70)

    # Check for custom parser
    parser_config = db.get_parser_config(site_name)
    if parser_config:
        print(f"✓ Has custom parser: {parser_config}")

    # Try to fetch the page
    soup = scraper.fetch_page(url)
    if not soup:
        print(f"❌ FAILED: Could not fetch page")
        return {'site_name': site_name, 'status': 'fetch_failed', 'jobs': 0}

    print(f"✓ Page fetched successfully")

    # Try scraping
    if parser_config:
        jobs = scraper.scrape_with_config(url, parser_config)
    else:
        jobs = scraper.auto_detect_jobs(url)

    print(f"Jobs found: {len(jobs)}")

    if jobs:
        print(f"\nSample job:")
        job = jobs[0]
        print(f"  Title: {job.get('title', 'NO TITLE')[:80]}")
        print(f"  URL: {job.get('url', 'NO URL')[:80]}")
        print(f"  Description: {job.get('description', 'NO DESCRIPTION')[:100] if job.get('description') else 'NO DESCRIPTION'}")
        print(f"  Location: {job.get('location', 'NO LOCATION')}")
        return {'site_name': site_name, 'status': 'working', 'jobs': len(jobs), 'has_description': bool(job.get('description'))}
    else:
        print(f"❌ No jobs found")
        return {'site_name': site_name, 'status': 'no_jobs', 'jobs': 0}

def main():
    scraper = JobScraper()
    db = JobDatabase()

    # Test sites with no jobs
    test_sites = [
        ("Gates Foundation", "https://gatesfoundation.wd1.myworkdayjobs.com/en-US/Gates"),
        ("Brookings Institution", "https://interns-brookings.icims.com/jobs/intro"),
        ("Freedom House", "https://phe.tbe.taleo.net/phe01/ats/careers/v2/jobSearch?act=redirectCwsV2&cws=39&org=FREEHOUS"),
        ("New America Foundation", "https://www.newamerica.org/about/jobs/"),
        ("Common Cause", "https://www.commoncause.org/careers/"),
        ("Democracy Alliance", "https://www.democracyalliance.org/careers/"),
    ]

    results = []
    for site_name, url in test_sites:
        result = test_site(scraper, db, site_name, url)
        results.append(result)

    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print('='*70)
    print(f"{'Site':<40} {'Status':<15} {'Jobs':>5}")
    print('-'*70)
    for r in results:
        print(f"{r['site_name']:<40} {r['status']:<15} {r['jobs']:>5}")

    fetch_failed = [r for r in results if r['status'] == 'fetch_failed']
    no_jobs = [r for r in results if r['status'] == 'no_jobs']
    working = [r for r in results if r['status'] == 'working']

    print(f"\nFetch failed: {len(fetch_failed)}")
    print(f"No jobs detected: {len(no_jobs)}")
    print(f"Working: {len(working)}")

if __name__ == "__main__":
    main()
