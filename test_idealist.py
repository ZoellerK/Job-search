#!/usr/bin/env python3
"""Test Idealist scraper to diagnose issues"""

from database import JobDatabase
from scraper import JobScraper

def test_idealist():
    db = JobDatabase()
    scraper = JobScraper()

    # Get the parser config
    parser_config = db.get_parser_config("Idealist")
    print("Current Idealist parser config:")
    print(parser_config)
    print()

    # Test the URL
    url = "https://www.idealist.org/en/jobs"
    print(f"Testing URL: {url}\n")

    # Get page structure info
    print("=" * 60)
    print("PAGE STRUCTURE ANALYSIS")
    print("=" * 60)
    page_info = scraper.test_selectors(url)
    if 'error' in page_info:
        print(f"ERROR: {page_info['error']}")
    else:
        print(f"Page title: {page_info['title']}")
        print(f"Total links: {page_info['links_count']}")
        print(f"\nCommon tags:")
        for tag, count in page_info['common_tags'].items():
            print(f"  {tag}: {count}")
        print(f"\nTop 10 common classes:")
        for cls, count in page_info['common_classes']:
            print(f"  {cls}: {count}")

    # Try scraping with current config
    print(f"\n" + "=" * 60)
    print("SCRAPING WITH CURRENT PARSER CONFIG")
    print("=" * 60)
    if parser_config:
        jobs = scraper.scrape_with_config(url, parser_config)
        print(f"Jobs found with custom parser: {len(jobs)}")
        if jobs:
            print("\nFirst job:")
            print(jobs[0])
    else:
        print("No parser config found")

    # Try auto-detection
    print(f"\n" + "=" * 60)
    print("SCRAPING WITH AUTO-DETECTION")
    print("=" * 60)
    jobs_auto = scraper.auto_detect_jobs(url)
    print(f"Jobs found with auto-detection: {len(jobs_auto)}")
    if jobs_auto:
        print(f"\nFirst 3 jobs:")
        for i, job in enumerate(jobs_auto[:3], 1):
            print(f"\n{i}. {job.get('title', 'NO TITLE')}")
            print(f"   URL: {job.get('url', 'NO URL')}")
            print(f"   Location: {job.get('location', 'N/A')}")
            desc = job.get('description', 'N/A')
            if desc and desc != 'N/A':
                print(f"   Description: {desc[:100]}...")

if __name__ == "__main__":
    test_idealist()
