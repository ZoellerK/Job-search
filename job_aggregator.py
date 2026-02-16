#!/usr/bin/env python3
"""
Job Posting Aggregator - Main Script
Scrapes job postings from multiple sources and generates RSS feed
"""

import csv
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict

from database import JobDatabase
from scraper import JobScraper
from feed_generator import RSSFeedGenerator
from salary_extractor import extract_salary
from ats_parsers import detect_ats, parse_ats_page

logger = logging.getLogger(__name__)


def configure_logging(level: str = "INFO"):
    """Set up structured logging to console and file."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (rotating-ish: just append for simplicity)
    try:
        fh = logging.FileHandler("job_aggregator.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # If we can't write a log file, carry on


class JobAggregator:
    """Main orchestrator for job aggregation"""

    def __init__(self, config_file: str = "config.json", sites_file: str = "sites.csv"):
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
        sites = []
        try:
            with open(self.sites_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('active', '').lower() in ['yes', 'true', '1']:
                        sites.append(row)
        except FileNotFoundError:
            logger.error("Sites file not found: %s", self.sites_file)
            return []
        return sites

    def scrape_site(self, site: Dict) -> Dict:
        """Scrape a single site, record health, return results."""
        site_name = site['site_name']
        url = site['url']
        keywords = site.get('keywords', '')
        scrape_details = site.get('scrape_details', 'no').lower() in ['yes', 'true', '1']

        try:
            parser_config = self.db.get_parser_config(site_name)

            if parser_config:
                jobs = self.scraper.scrape_with_config(url, parser_config)
            else:
                # Try ATS-specific parser first, fall back to generic
                ats = detect_ats(url)
                if ats:
                    soup = self.scraper.fetch_page(url)
                    if soup:
                        from urllib.parse import urlparse as _urlparse
                        base = f"{_urlparse(url).scheme}://{_urlparse(url).netloc}"
                        jobs = parse_ats_page(ats, soup, base)
                        if jobs:
                            logger.info("%s: ATS parser (%s) found %d jobs", site_name, ats, len(jobs))
                    else:
                        jobs = []
                    # Fall back to generic if ATS parser found nothing
                    if not jobs:
                        jobs = self.scraper.auto_detect_jobs(url)
                else:
                    jobs = self.scraper.auto_detect_jobs(url)

            if scrape_details and jobs:
                logger.info("Scraping detail pages for %s (%d jobs)", site_name, min(len(jobs), 20))
                jobs = self.scraper.enrich_jobs_with_details(jobs, max_jobs=20)

            # Extract salary from description text when no explicit salary field
            for job in jobs:
                if not job.get('salary') and job.get('description'):
                    extracted = extract_salary(job['description'])
                    if extracted:
                        job['salary'] = extracted

            new_jobs_count = 0
            dedup_skipped = 0

            for job in jobs:
                if keywords:
                    job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
                    if not any(kw.strip().lower() in job_text for kw in keywords.split(',')):
                        continue

                # Cross-site dedup check
                existing = self.db.find_similar_job(job.get('title', ''), site_name)
                if existing:
                    dedup_skipped += 1
                    logger.debug(
                        "Dedup: '%s' from %s matches '%s' from %s",
                        job.get('title'), site_name,
                        existing['title'], existing['site_name']
                    )
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

            # Mark all scraped URLs as "seen" for staleness tracking
            seen_urls = [j.get('url') for j in jobs if j.get('url')]
            if seen_urls:
                self.db.mark_jobs_seen(seen_urls)

            # Record health
            self.db.record_scrape_result(
                site_name=site_name,
                success=True,
                jobs_found=len(jobs),
            )

            result = {
                'site_name': site_name,
                'success': True,
                'new_jobs': new_jobs_count,
                'total_found': len(jobs),
                'dedup_skipped': dedup_skipped,
                'error': None
            }
            if dedup_skipped:
                logger.info("%s: %d new, %d dedup-skipped", site_name, new_jobs_count, dedup_skipped)

            return result

        except Exception as e:
            logger.error("Failed to scrape %s: %s", site_name, e, exc_info=True)
            self.db.record_scrape_result(
                site_name=site_name,
                success=False,
                error_message=str(e),
            )
            return {
                'site_name': site_name,
                'success': False,
                'new_jobs': 0,
                'total_found': 0,
                'dedup_skipped': 0,
                'error': str(e)
            }

    def scrape_all(self) -> Dict:
        sites = self.load_sites()
        if not sites:
            logger.warning("No active sites found in %s", self.sites_file)
            return {
                'total_new_jobs': 0,
                'successful_sites': 0,
                'failed_sites': 0,
                'site_results': []
            }

        logger.info("Starting job aggregation for %d sites", len(sites))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.scrape_site, site): site for site in sites}
            site_results = [f.result() for f in as_completed(futures)]

        site_results.sort(key=lambda r: r['site_name'])

        for result in site_results:
            status = "OK" if result['success'] else "FAIL"
            jobs_str = f"{result['new_jobs']} new" if result['new_jobs'] else "no new jobs"
            error_str = f" -- {result['error']}" if result['error'] else ""
            logger.info("  [%s] %s: %s%s", status, result['site_name'], jobs_str, error_str)

        total_new_jobs = sum(r['new_jobs'] for r in site_results)
        successful_sites = sum(1 for r in site_results if r['success'])
        failed_sites = sum(1 for r in site_results if not r['success'])

        logger.info(
            "Scraping complete: %d new jobs, %d/%d sites succeeded",
            total_new_jobs, successful_sites, len(sites)
        )

        return {
            'total_new_jobs': total_new_jobs,
            'successful_sites': successful_sites,
            'failed_sites': failed_sites,
            'site_results': site_results
        }

    def generate_feed(self, max_items: int = None) -> str:
        if max_items is None:
            max_items = self.config['output']['max_items']

        jobs = self.db.get_recent_jobs(limit=max_items)
        logger.info("Generating RSS feed with %d jobs", len(jobs))

        output_file = self.config['output']['feed_file']
        self.feed_gen.generate_feed(jobs, output_file)

        logger.info("RSS feed saved to %s", output_file)
        return output_file

    def generate_preview(self) -> str:
        jobs = self.db.get_recent_jobs(limit=50)
        output_file = "preview.html"
        self.feed_gen.generate_html_preview(jobs, output_file)
        logger.info("HTML preview saved to %s", output_file)
        return output_file

    def show_stats(self):
        stats = self.db.get_stats()
        logger.info(
            "Stats: %d total jobs, %d today, %d this week, %d sites",
            stats['total_jobs'], stats['jobs_today'],
            stats['jobs_this_week'], stats['total_sites']
        )

    def check_site_health(self) -> List[Dict]:
        """
        Check for persistently failing sites and return alerts.
        These get surfaced in the RSS feed summary so you see them in Feedly.
        """
        failing = self.db.get_failing_sites(consecutive_failures=3)
        if failing:
            logger.warning("=== SITE HEALTH ALERTS ===")
            for site in failing:
                logger.warning(
                    "  %s: %d consecutive failures (last error: %s)",
                    site['site_name'],
                    site['consecutive_failures'],
                    site['last_error']
                )
        return failing

    def run_full_update(self):
        """Run complete update cycle: scrape, cleanup, generate feed, show stats"""
        logger.info("Starting full update cycle")

        # Clean up old data and flag stale listings
        deleted = self.db.cleanup_old_jobs(days_to_keep=90)
        if deleted:
            logger.info("Deleted %d jobs older than 90 days", deleted)
        self.db.cleanup_old_health_records(days_to_keep=30)
        stale = self.db.mark_stale_jobs(stale_after_days=30)
        if stale:
            logger.info("Flagged %d stale jobs (not seen in 30+ days)", stale)

        # Scrape all sites
        scrape_results = self.scrape_all()

        # Check site health — alerts go into the feed summary
        health_alerts = self.check_site_health()

        # Generate RSS feed with summary + health alerts
        self.generate_feed_with_summary(scrape_results, health_alerts)

        # Generate HTML preview
        self.generate_preview()

        # Show stats
        self.show_stats()

        logger.info("Update complete: %d new jobs found", scrape_results['total_new_jobs'])

    def generate_feed_with_summary(self, scrape_results: Dict,
                                    health_alerts: List[Dict] = None):
        """Generate RSS feed with optional scraping summary and health alerts."""
        max_items = self.config['output']['max_items']
        jobs = self.db.get_recent_jobs(limit=max_items)

        # Exclude stale jobs from the feed
        jobs = [j for j in jobs if not j.get('stale')]

        stale_count = len(self.db.get_stale_jobs())
        include_summary = self.config['feed'].get('include_summary', True)

        if include_summary and (scrape_results['total_new_jobs'] > 0 or health_alerts):
            summary_job = self.feed_gen.build_summary_item(
                scrape_results, health_alerts=health_alerts or [],
                stale_count=stale_count,
            )
            jobs = [summary_job] + jobs
            logger.info("Including summary + %d jobs in feed (%d stale excluded)", len(jobs) - 1, stale_count)
        else:
            logger.info("Including %d jobs in feed", len(jobs))

        output_file = self.config['output']['feed_file']
        self.feed_gen.generate_feed(jobs, output_file)
        logger.info("RSS feed saved to %s", output_file)

    def export(self, output_file: str, fmt: str = "csv",
               limit: int = None, site_name: str = None):
        """Export jobs to a file."""
        self.db.export_jobs(output_file, fmt=fmt, limit=limit, site_name=site_name)
        logger.info("Exported to %s", output_file)

    def show_health(self):
        """Print site health summary to console."""
        summary = self.db.get_site_health_summary()
        if not summary:
            logger.info("No site health data yet. Run a scrape first.")
            return

        logger.info("=== Site Health (last 7 days) ===")
        for s in summary:
            status = "OK" if s['failures'] == 0 else "WARN"
            logger.info(
                "  [%s] %s: %d/%d succeeded, %d jobs found",
                status, s['site_name'], s['successes'], s['total_scrapes'],
                s['total_jobs_found']
            )

        failing = self.db.get_failing_sites(consecutive_failures=3)
        if failing:
            logger.warning("--- Persistently failing (3+ consecutive) ---")
            for site in failing:
                logger.warning(
                    "  %s: %d failures, last error: %s",
                    site['site_name'], site['consecutive_failures'], site['last_error']
                )


def main():
    configure_logging()

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
            elif command == "health":
                aggregator.show_health()
            elif command == "export":
                fmt = "csv"
                output = "jobs_export.csv"
                if len(sys.argv) > 2:
                    fmt = sys.argv[2].lower()
                    output = f"jobs_export.{fmt}"
                if len(sys.argv) > 3:
                    output = sys.argv[3]
                aggregator.export(output, fmt=fmt)
            elif command == "stale":
                stale_jobs = aggregator.db.get_stale_jobs()
                if stale_jobs:
                    logger.info("=== Stale Jobs (not seen in 30+ days) ===")
                    for j in stale_jobs:
                        logger.info("  [%s] %s — last seen %s", j['site_name'], j['title'], j.get('last_seen_date', 'unknown'))
                else:
                    logger.info("No stale jobs found.")
            else:
                print(f"Unknown command: {command}")
                print("\nAvailable commands:")
                print("  scrape  - Scrape all active sites")
                print("  feed    - Generate RSS feed from database")
                print("  preview - Generate HTML preview")
                print("  stats   - Show database statistics")
                print("  update  - Run full update (scrape + feed + preview)")
                print("  health  - Show site health summary")
                print("  stale   - Show stale job listings")
                print("  export [csv|json] [filename] - Export jobs")
                sys.exit(1)
        else:
            aggregator.run_full_update()

        logger.info("Job aggregator completed successfully")
        sys.exit(0)

    except FileNotFoundError as e:
        logger.error("Required file not found: %s", e)
        sys.exit(1)
    except KeyError as e:
        logger.error("Missing required configuration key: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s: %s", type(e).__name__, e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
