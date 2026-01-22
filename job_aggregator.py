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
            site: Dictionary with site_name, url, keywords

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

        print(f"\n🔍 Scraping {site_name}...")
        print(f"   URL: {url}")

        try:
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
            return {
                'site_name': site_name,
                'success': True,
                'new_jobs': new_jobs_count,
                'error': None
            }

        except Exception as e:
            error_msg = str(e)
            print(f"   ✗ Error: {error_msg}")
            return {
                'site_name': site_name,
                'success': False,
                'new_jobs': 0,
                'error': error_msg
            }

    def scrape_all(self) -> Dict:
        """
        Scrape all active sites

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

        site_results = []
        total_new_jobs = 0
        successful_sites = 0
        failed_sites = 0

        for site in sites:
            result = self.scrape_site(site)
            site_results.append(result)
            total_new_jobs += result['new_jobs']
            if result['success']:
                successful_sites += 1
            else:
                failed_sites += 1

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

        # Get recent jobs
        max_items = self.config['output']['max_items']
        jobs = self.db.get_recent_jobs(limit=max_items)

        # Check if summary should be included
        include_summary = self.config['feed'].get('include_summary', True)

        if include_summary and scrape_results['total_new_jobs'] > 0:
            # Create condensed summary entry
            from datetime import datetime
            import pytz

            summary_parts = []
            summary_parts.append(f"<h3>📊 Update Summary</h3>")
            summary_parts.append(f"<p><strong>New Jobs Found:</strong> {scrape_results['total_new_jobs']}</p>")
            summary_parts.append(f"<p><strong>Sites Checked:</strong> {scrape_results['successful_sites']}/{scrape_results['successful_sites'] + scrape_results['failed_sites']}</p>")

            # Only show failures if there are any
            if scrape_results['failed_sites'] > 0:
                summary_parts.append(f"<p><strong>⚠️ Failed Sites:</strong> {scrape_results['failed_sites']}</p>")
                failed_sites = [r['site_name'] for r in scrape_results['site_results'] if not r['success']]
                summary_parts.append(f"<p style='font-size: 0.9em; color: #666;'>{', '.join(failed_sites)}</p>")

            # Condensed site breakdown - only sites with new jobs
            sites_with_jobs = [r for r in scrape_results['site_results'] if r['success'] and r['new_jobs'] > 0]
            if sites_with_jobs:
                summary_parts.append("<details><summary><strong>Sites with New Jobs</strong></summary>")
                summary_parts.append("<ul>")
                for result in sorted(sites_with_jobs, key=lambda x: x['new_jobs'], reverse=True):
                    summary_parts.append(f"<li><strong>{result['site_name']}</strong>: {result['new_jobs']} new</li>")
                summary_parts.append("</ul></details>")

            # Create summary job entry
            summary_job = {
                'title': f"📊 Update - {scrape_results['total_new_jobs']} New Jobs Found",
                'url': self.config['feed']['link'],
                'site_name': 'System Update',
                'description': '\n'.join(summary_parts),
                'discovered_date': datetime.now(pytz.UTC).isoformat()
            }

            # Insert summary at the beginning
            jobs = [summary_job] + jobs
            print(f"   Including summary + {len(jobs)-1} jobs in feed")
        else:
            print(f"   Including {len(jobs)} jobs in feed")

        output_file = self.config['output']['feed_file']
        self.feed_gen.generate_feed(jobs, output_file)

        print(f"   ✓ RSS feed saved to {output_file}")


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
