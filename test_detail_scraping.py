#!/usr/bin/env python3
"""
Test script for detail page scraping functionality
Demonstrates how the enhanced scraper extracts job descriptions from individual job pages
"""

from scraper import JobScraper
from database import JobDatabase

def test_detail_scraping():
    """Test detail page scraping for a few job URLs"""

    print("\n" + "="*70)
    print("Testing Detail Page Scraping")
    print("="*70)

    # Initialize scraper
    scraper = JobScraper()

    # Test URLs from different sites
    test_urls = [
        "https://pac.org/job/manager-corporate-communications-4",
        "https://pac.org/job/associate-general-counsel-senior",
        "https://pac.org/job/director-compliance-3"
    ]

    print("\nNote: Some sites may block automated requests, which is expected.\n")

    for i, url in enumerate(test_urls, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}/{len(test_urls)}: {url}")
        print(f"{'='*70}\n")

        # Scrape job details
        details = scraper.scrape_job_details(url)

        if details:
            print("✓ Successfully scraped job details:")
            print(f"\n  Description Length: {len(details.get('description', ''))} characters")

            if details.get('description'):
                preview = details['description'][:200] + "..." if len(details['description']) > 200 else details['description']
                print(f"  Description Preview: {preview}")

            if details.get('location'):
                print(f"  Location: {details['location']}")

            if details.get('salary'):
                print(f"  Salary: {details['salary']}")

            if details.get('job_type'):
                print(f"  Job Type: {details['job_type']}")

            if details.get('posted_date'):
                print(f"  Posted Date: {details['posted_date']}")
        else:
            print("✗ No details could be extracted (site may block scraping)")

    print("\n" + "="*70)
    print("Test Complete")
    print("="*70 + "\n")


def test_job_enrichment():
    """Test enriching a list of jobs with detail page scraping"""

    print("\n" + "="*70)
    print("Testing Job List Enrichment")
    print("="*70)

    # Initialize scraper
    scraper = JobScraper()

    # Create sample jobs (simulating what would come from a listing page)
    sample_jobs = [
        {
            'title': 'Manager, Corporate Communications',
            'url': 'https://pac.org/job/manager-corporate-communications-4',
            'description': None,  # No description from listing page
            'location': None
        },
        {
            'title': 'Associate General Counsel Senior',
            'url': 'https://pac.org/job/associate-general-counsel-senior',
            'description': None,
            'location': None
        }
    ]

    print(f"\nEnriching {len(sample_jobs)} jobs with detail page information...")
    print("Note: This will make individual requests to each job page.\n")

    # Enrich jobs (limit to 2 for testing)
    enriched_jobs = scraper.enrich_jobs_with_details(sample_jobs, max_jobs=2)

    print("\n" + "="*70)
    print("Enrichment Results")
    print("="*70)

    for i, job in enumerate(enriched_jobs, 1):
        print(f"\nJob {i}: {job['title']}")
        print(f"  URL: {job['url']}")

        if job.get('description'):
            desc_len = len(job['description'])
            print(f"  ✓ Description: {desc_len} characters")
            preview = job['description'][:150] + "..." if desc_len > 150 else job['description']
            print(f"    Preview: {preview}")
        else:
            print(f"  ✗ No description extracted")

        if job.get('location'):
            print(f"  ✓ Location: {job['location']}")

        if job.get('salary'):
            print(f"  ✓ Salary: {job['salary']}")

        if job.get('job_type'):
            print(f"  ✓ Job Type: {job['job_type']}")

    print("\n" + "="*70 + "\n")


def show_database_stats():
    """Show current database statistics"""

    print("\n" + "="*70)
    print("Current Database Statistics")
    print("="*70)

    db = JobDatabase("jobs.db")
    stats = db.get_stats()

    print(f"\nTotal jobs in database: {stats['total_jobs']}")
    print(f"Jobs discovered today: {stats['jobs_today']}")
    print(f"Jobs discovered this week: {stats['jobs_this_week']}")
    print(f"Sites with jobs: {stats['total_sites']}")

    # Check how many jobs have descriptions
    import sqlite3
    conn = sqlite3.connect("jobs.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE description IS NOT NULL AND description != ''")
    jobs_with_desc = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE details_scraped = 1")
    jobs_with_details = cursor.fetchone()[0]

    conn.close()

    print(f"\nJobs with descriptions: {jobs_with_desc} ({jobs_with_desc*100//stats['total_jobs'] if stats['total_jobs'] > 0 else 0}%)")
    print(f"Jobs with scraped details: {jobs_with_details}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "details":
            test_detail_scraping()
        elif command == "enrich":
            test_job_enrichment()
        elif command == "stats":
            show_database_stats()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  details - Test scraping individual job detail pages")
            print("  enrich  - Test enriching a list of jobs")
            print("  stats   - Show database statistics")
            sys.exit(1)
    else:
        # Run all tests
        show_database_stats()
        test_detail_scraping()
        test_job_enrichment()
        show_database_stats()
