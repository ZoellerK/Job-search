#!/usr/bin/env python3
"""
Job Posting Aggregator - Main Script
Scrapes job postings from multiple sources and generates RSS feed
"""

import csv
import json
import sys
from typing import List, Dict
from database import JobDatabase
from scraper import JobScraper
from feed_generator import RSSFeedGenerator


class JobAggregator:
    """Main orchestrator for job aggregation"""

    def __init__(self, config_file: str = "config.json", sites_file: str = "sites.csv"):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        self.sites_file = sites_file
        self.db = JobDatabase(self.config['database']['path'])
        self.scraper = JobScraper(
            user_agent=self.config['scraping']['user_agent'],
            timeout=self.config['scraping']['timeout'],
            retry_attempts=self.config['scraping']['retry_attempts']
        )
        self.feed_gen = RSSFeedGenerator(
            title=self.config['feed']['title'],
            description=self.config['feed']['description'],
            link=self.config['feed']['link'],
            author=self.config['feed']['author']
        )

    def load_sites(self) -> List[Dict]:
        """Load sites to scrape from CSV file"""
        sites = []
        try:
            with open(self.sites_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('active', '').lower() in ['yes', 'true', '1']:
                        sites.append(row)
        except FileNotFoundError:
            print(f"Error: {self.sites_file} not found")
            return []
        return sites

    def scrape_site(self, site: Dict) -> int:
        """
        Scrape a single site and add new jobs to database

        Args:
            site: Dictionary with site_name, url, keywords

        Returns:
            Number of new jobs found
        """
        site_name = site['site_name']
        url = site['url']
        keywords = site.get('keywords', '')

        print(f"\n🔍 Scraping {site_name}...")
        print(f"   URL: {url}")

        # Check if we have a saved parser config for this site
        parser_config = self.db.get_parser_config(site_name)

        if parser_config:
            print(f"   Using saved parser configuration")
            jobs = self.scraper.scrape_with_config(url, parser_config)
        else:
            print(f"   Using auto-detection")
            jobs = self.scraper.auto_detect_jobs(url)

        print(f"   Found {len(jobs)} potential job listings")

        # Add new jobs to database
        new_jobs_count = 0
        for job in jobs:
            # Filter by keywords if specified
            if keywords:
                job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
                if not any(kw.strip().lower() in job_text for kw in keywords.split(',')):
                    continue

            # Add to database
            added = self.db.add_job(
                site_name=site_name,
                url=job.get('url', url),
                title=job.get('title', 'Unknown Position'),
                description=job.get('description'),
                location=job.get('location'),
                posted_date=job.get('posted_date'),
                keywords=keywords
            )

            if added:
                new_jobs_count += 1
                print(f"   ✓ New job: {job.get('title', 'Unknown')}")

        print(f"   Added {new_jobs_count} new jobs to database")
        return new_jobs_count

    def scrape_all(self) -> int:
        """
        Scrape all active sites

        Returns:
            Total number of new jobs found
        """
        sites = self.load_sites()
        if not sites:
            print("No active sites found in sites.csv")
            return 0

        print(f"\n{'='*60}")
        print(f"Starting job aggregation for {len(sites)} sites")
        print(f"{'='*60}")

        total_new_jobs = 0
        for site in sites:
            try:
                new_jobs = self.scrape_site(site)
                total_new_jobs += new_jobs
            except Exception as e:
                print(f"   ✗ Error scraping {site['site_name']}: {e}")

        print(f"\n{'='*60}")
        print(f"Scraping complete! Total new jobs: {total_new_jobs}")
        print(f"{'='*60}\n")

        return total_new_jobs

    def generate_feed(self, max_items: int = None) -> str:
        """
        Generate RSS feed from database

        Args:
            max_items: Maximum number of items to include (default from config)

        Returns:
            Path to generated feed file
        """
        if max_items is None:
            max_items = self.config['output']['max_items']

        print(f"\n📡 Generating RSS feed...")

        jobs = self.db.get_recent_jobs(limit=max_items)
        print(f"   Including {len(jobs)} jobs in feed")

        output_file = self.config['output']['feed_file']
        self.feed_gen.generate_feed(jobs, output_file)

        print(f"   ✓ RSS feed saved to {output_file}")
        return output_file

    def generate_preview(self) -> str:
        """Generate HTML preview of recent jobs"""
        print(f"\n📄 Generating HTML preview...")

        jobs = self.db.get_recent_jobs(limit=50)
        output_file = "preview.html"
        self.feed_gen.generate_html_preview(jobs, output_file)

        print(f"   ✓ HTML preview saved to {output_file}")
        return output_file

    def show_stats(self):
        """Display database statistics"""
        stats = self.db.get_stats()

        print(f"\n📊 Database Statistics")
        print(f"{'='*40}")
        print(f"Total jobs tracked: {stats['total_jobs']}")
        print(f"Jobs discovered today: {stats['jobs_today']}")
        print(f"Sites monitored: {stats['total_sites']}")
        print(f"{'='*40}\n")

    def run_full_update(self):
        """Run complete update cycle: scrape, generate feed, show stats"""
        print("\n🚀 Starting full update cycle...")

        # Scrape all sites
        new_jobs = self.scrape_all()

        # Generate RSS feed
        self.generate_feed()

        # Generate HTML preview
        self.generate_preview()

        # Show stats
        self.show_stats()

        print(f"✅ Update complete! Found {new_jobs} new jobs.\n")


def main():
    """Main entry point"""
    aggregator = JobAggregator()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "scrape":
            aggregator.scrape_all()
        elif command == "feed":
            aggregator.generate_feed()
        elif command == "preview":
            aggregator.generate_preview()
        elif command == "stats":
            aggregator.show_stats()
        elif command == "update":
            aggregator.run_full_update()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  scrape  - Scrape all active sites")
            print("  feed    - Generate RSS feed from database")
            print("  preview - Generate HTML preview")
            print("  stats   - Show database statistics")
            print("  update  - Run full update (scrape + feed + preview)")
    else:
        # Default: run full update
        aggregator.run_full_update()


if __name__ == "__main__":
    main()
