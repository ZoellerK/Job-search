#!/usr/bin/env python3
"""
Job Posting Aggregator - Main Script
Scrapes job postings from multiple sources and generates RSS feed
"""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict

import pytz

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
            author=self.config['feed']['author'],
            include_site_in_title=self.config['feed'].get('include_site_in_title', True),
            simple_descriptions=self.config['feed'].get('simple_descriptions', False)
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

    def scrape_site(self, site: Dict) -> Dict:
        """
        Scrape a single site and add new jobs to database

        Args:
            site: Dictionary with site_name, url, keywords, scrape_details

        Returns:
            Dictionary with scraping results: {
                'site_name': str,
                'success': bool,
                'new_jobs': int,
                'error': str or None
            }
        """
        site_name = site['site_name']
        url = site['url']
        keywords = site.get('keywords', '')
        scrape_details = site.get('scrape_details', 'no').lower() in ['yes', 'true', '1']

        try:
            parser_config = self.db.get_parser_config(site_name)

            if parser_config:
                jobs = self.scraper.scrape_with_config(url, parser_config)
            else:
                jobs = self.scraper.auto_detect_jobs(url)

            # If scrape_details is enabled, enrich jobs with detail page information
            if scrape_details and jobs:
                print(f"   → Scraping detail pages for {site_name} ({len(jobs[:20])} jobs)...")
                jobs = self.scraper.enrich_jobs_with_details(jobs, max_jobs=20)

            new_jobs_count = 0
            for job in jobs:
                if keywords:
                    job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
                    if not any(kw.strip().lower() in job_text for kw in keywords.split(',')):
                        continue

                added = self.db.add_job(
                    site_name=site_name,
                    url=job.get('url', url),
                    title=job.get('title', 'Unknown Position'),
                    description=job.get('description'),
                    location=job.get('location'),
                    posted_date=job.get('posted_date'),
                    keywords=keywords,
                    salary=job.get('salary'),
                    job_type=job.get('job_type'),
                    details_scraped=scrape_details
                )

                if added:
                    new_jobs_count += 1

            return {
                'site_name': site_name,
                'success': True,
                'new_jobs': new_jobs_count,
                'error': None
            }

        except Exception as e:
            return {
                'site_name': site_name,
                'success': False,
                'new_jobs': 0,
                'error': str(e)
            }

    def scrape_all(self) -> Dict:
        """
        Scrape all active sites in parallel

        Returns:
            Dictionary with results: {
                'total_new_jobs': int,
                'successful_sites': int,
                'failed_sites': int,
                'site_results': List[Dict]
            }
        """
        sites = self.load_sites()
        if not sites:
            print("No active sites found in sites.csv")
            return {
                'total_new_jobs': 0,
                'successful_sites': 0,
                'failed_sites': 0,
                'site_results': []
            }

        print(f"\n{'='*60}")
        print(f"Starting job aggregation for {len(sites)} sites")
        print(f"{'='*60}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.scrape_site, site): site for site in sites}
            site_results = [f.result() for f in as_completed(futures)]

        # Sort for deterministic output
        site_results.sort(key=lambda r: r['site_name'])

        for result in site_results:
            status = "✓" if result['success'] else "✗"
            jobs_str = f"{result['new_jobs']} new" if result['new_jobs'] else "no new jobs"
            error_str = f" — {result['error']}" if result['error'] else ""
            print(f"  {status} {result['site_name']}: {jobs_str}{error_str}")

        total_new_jobs = sum(r['new_jobs'] for r in site_results)
        successful_sites = sum(1 for r in site_results if r['success'])
        failed_sites = sum(1 for r in site_results if not r['success'])

        print(f"\n{'='*60}")
        print(f"Scraping complete! Total new jobs: {total_new_jobs}")
        print(f"Successful: {successful_sites}/{len(sites)} sites")
        if failed_sites > 0:
            print(f"Failed: {failed_sites} sites")
        print(f"{'='*60}\n")

        return {
            'total_new_jobs': total_new_jobs,
            'successful_sites': successful_sites,
            'failed_sites': failed_sites,
            'site_results': site_results
        }

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
        """Run complete update cycle: scrape, cleanup, generate feed, show stats"""
        print("\n🚀 Starting full update cycle...")

        # Clean up old jobs (keep last 90 days)
        print("\n🧹 Cleaning up old jobs...")
        deleted = self.db.cleanup_old_jobs(days_to_keep=90)
        if deleted > 0:
            print(f"   Deleted {deleted} jobs older than 90 days")
        else:
            print(f"   No old jobs to delete")

        # Scrape all sites
        scrape_results = self.scrape_all()

        # Generate RSS feed with scraping summary
        self.generate_feed_with_summary(scrape_results)

        # Generate HTML preview
        self.generate_preview()

        # Show stats
        self.show_stats()

        print(f"✅ Update complete! Found {scrape_results['total_new_jobs']} new jobs.\n")

    def generate_feed_with_summary(self, scrape_results: Dict):
        """Generate RSS feed with optional scraping summary at the top"""
        print(f"\n📡 Generating RSS feed...")

        max_items = self.config['output']['max_items']
        jobs = self.db.get_recent_jobs(limit=max_items)

        include_summary = self.config['feed'].get('include_summary', True)

        if include_summary and scrape_results['total_new_jobs'] > 0:
            summary_job = self.feed_gen.build_summary_item(scrape_results)
            jobs = [summary_job] + jobs
            print(f"   Including summary + {len(jobs)-1} jobs in feed")
        else:
            print(f"   Including {len(jobs)} jobs in feed")

        output_file = self.config['output']['feed_file']
        self.feed_gen.generate_feed(jobs, output_file)

        print(f"   ✓ RSS feed saved to {output_file}")


def main():
    """Main entry point"""
    try:
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
                sys.exit(1)
        else:
            # Default: run full update
            aggregator.run_full_update()

        print("\n✅ Job aggregator completed successfully!")
        sys.exit(0)

    except FileNotFoundError as e:
        print(f"\n❌ Error: Required file not found: {e}")
        print("Please ensure config.json and sites.csv exist in the working directory.")
        sys.exit(1)
    except KeyError as e:
        print(f"\n❌ Error: Missing required configuration key: {e}")
        print("Please check your config.json file.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: Job aggregator failed with unexpected error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\nThe job aggregator encountered an error but this may not prevent feed generation.")
        print("Check the error above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
