#!/usr/bin/env python3
"""
Site Setup Tool - Helps configure new job sites
"""

import sys
import csv
import json
import os
from urllib.parse import urlparse
from scraper import JobScraper
from database import JobDatabase
from ats_parsers import detect_ats, parse_ats_page


class SiteSetup:
    """Interactive tool for setting up new job sites"""

    def __init__(self):
        self.scraper = JobScraper()
        self.db = JobDatabase()

    def test_url(self, url: str):
        """Test a URL and display information about its structure"""
        print(f"\n🔍 Testing URL: {url}")
        print("=" * 60)

        # Get page structure info
        info = self.scraper.test_selectors(url)

        if 'error' in info:
            print(f"❌ Error: {info['error']}")
            return

        print(f"\n📄 Page Title: {info['title']}")
        print(f"\n🔗 Total Links: {info['links_count']}")

        print(f"\n🏷️  Most Common Classes:")
        for cls, count in info['common_classes'][:10]:
            print(f"   {cls}: {count} occurrences")

        print(f"\n📦 Common Tags:")
        for tag, count in info['common_tags'].items():
            print(f"   <{tag}>: {count} occurrences")

    def auto_detect(self, url: str, save_to_csv: bool = False):
        """Auto-detect jobs on a URL and optionally save to sites.csv"""
        print(f"\n🤖 Auto-detecting job listings on: {url}")
        print("=" * 60)

        # Try ATS-specific parser first for better results
        ats = detect_ats(url)
        jobs = []
        if ats:
            print(f"\n🔌 Detected ATS platform: {ats}")
            soup = self.scraper.fetch_page(url)
            if soup:
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                jobs = parse_ats_page(ats, soup, base)
                if jobs:
                    print(f"   ATS parser found {len(jobs)} jobs")
                else:
                    print("   ATS parser returned nothing, falling back to generic detection")

        if not jobs:
            jobs = self.scraper.auto_detect_jobs(url)

        if not jobs:
            print("\n❌ No job listings detected automatically.")
            print("\nTips:")
            print("  - Make sure the URL is a careers/jobs page")
            print("  - The page might require custom configuration")
            print("  - Use 'python setup_site.py test <url>' to analyze the page structure")
            return

        print(f"\n✅ Found {len(jobs)} potential job listings:\n")

        for i, job in enumerate(jobs[:10], 1):  # Show first 10
            print(f"{i}. {job.get('title', 'No title')}")
            if job.get('location'):
                print(f"   Location: {job['location']}")
            if job.get('url'):
                print(f"   URL: {job['url'][:80]}...")
            print()

        if len(jobs) > 10:
            print(f"... and {len(jobs) - 10} more")

        if save_to_csv:
            self._save_to_sites_csv(url, jobs)

    def create_custom_config(self, url: str, site_name: str):
        """Interactive wizard to create custom parser configuration"""
        print(f"\n⚙️  Creating custom parser for: {site_name}")
        print("=" * 60)

        config = {}

        print("\nLet's configure the parser. Leave blank to skip a field.\n")

        # Job container
        print("1. Job Container (the element that wraps each job listing)")
        container_tag = input("   Container tag (e.g., div, li, article) [div]: ").strip() or "div"
        container_class = input("   Container class (e.g., job-listing): ").strip()

        if container_class:
            config['job_container'] = {
                'tag': container_tag,
                'class': container_class
            }
        else:
            print("   ⚠️  Warning: No container class specified. Auto-detection may not work well.")
            return None

        # Title
        print("\n2. Job Title")
        title_tag = input("   Title tag (e.g., h2, h3, a) [h3]: ").strip() or "h3"
        title_class = input("   Title class (optional): ").strip()

        config['title'] = {'tag': title_tag}
        if title_class:
            config['title']['class'] = title_class

        # URL
        print("\n3. Job URL")
        url_tag = input("   URL tag (usually 'a') [a]: ").strip() or "a"
        url_attr = input("   URL attribute [href]: ").strip() or "href"

        config['url'] = {
            'tag': url_tag,
            'attr': url_attr
        }

        # Location (optional)
        print("\n4. Location (optional)")
        loc_tag = input("   Location tag (e.g., span, div) [span]: ").strip() or "span"
        loc_class = input("   Location class: ").strip()

        if loc_class:
            config['location'] = {
                'tag': loc_tag,
                'class': loc_class
            }

        # Description (optional)
        print("\n5. Description (optional)")
        desc_tag = input("   Description tag (e.g., p, div) [p]: ").strip() or "p"
        desc_class = input("   Description class: ").strip()

        if desc_class:
            config['description'] = {
                'tag': desc_tag,
                'class': desc_class
            }

        # Save configuration
        print(f"\n📝 Parser Configuration:")
        print(json.dumps(config, indent=2))

        save = input("\n💾 Save this configuration? (y/n) [y]: ").strip().lower()
        if save != 'n':
            self.db.save_parser_config(site_name, url, config)
            print(f"✅ Configuration saved for {site_name}")

            # Test the configuration
            test = input("\n🧪 Test this configuration now? (y/n) [y]: ").strip().lower()
            if test != 'n':
                self._test_config(url, config)

        return config

    def _test_config(self, url: str, config: dict):
        """Test a parser configuration"""
        print(f"\n🧪 Testing parser configuration...")

        jobs = self.scraper.scrape_with_config(url, config)

        if not jobs:
            print("❌ No jobs found with this configuration")
            print("   Try adjusting the selectors")
            return

        print(f"✅ Found {len(jobs)} jobs:\n")

        for i, job in enumerate(jobs[:5], 1):  # Show first 5
            print(f"{i}. {job.get('title', 'No title')}")
            if job.get('location'):
                print(f"   Location: {job['location']}")
            if job.get('url'):
                print(f"   URL: {job['url'][:80]}...")
            print()

    def _save_to_sites_csv(self, url: str, jobs: list):
        """Helper to add URL to sites.csv"""
        site_name = input("\n📝 Enter a name for this site: ").strip()
        if not site_name:
            print("❌ Site name is required")
            return

        keywords = input("   Keywords to filter by (comma-separated, optional): ").strip()

        # Check for duplicates and create file if needed
        if os.path.exists('sites.csv'):
            with open('sites.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('url', '').strip() == url.strip():
                        print(f"\n⚠️  {url} is already in sites.csv as '{row.get('site_name', 'unknown')}'")
                        return
        else:
            with open('sites.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['site_name', 'url', 'active', 'keywords', 'scrape_details'])

        # Append new site
        try:
            with open('sites.csv', 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([site_name, url, 'yes', keywords, 'no'])

            print(f"\n✅ Added {site_name} to sites.csv")
            print(f"   Jobs detected: {len(jobs)}")
            print(f"   Status: Active")
        except Exception as e:
            print(f"❌ Error saving to sites.csv: {e}")


def main():
    """Main entry point"""
    setup = SiteSetup()

    if len(sys.argv) < 2:
        print("Site Setup Tool - Configure new job sites")
        print("\nUsage:")
        print("  python setup_site.py test <url>")
        print("    - Test a URL and show page structure")
        print()
        print("  python setup_site.py auto <url>")
        print("    - Auto-detect jobs and optionally add to sites.csv")
        print()
        print("  python setup_site.py config <url> <site_name>")
        print("    - Create custom parser configuration")
        print()
        print("Examples:")
        print("  python setup_site.py auto https://example.com/careers")
        print("  python setup_site.py config https://example.com/jobs 'Example Company'")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "test":
        if len(sys.argv) < 3:
            print("Error: URL required")
            print("Usage: python setup_site.py test <url>")
            sys.exit(1)
        url = sys.argv[2]
        setup.test_url(url)

    elif command == "auto":
        if len(sys.argv) < 3:
            print("Error: URL required")
            print("Usage: python setup_site.py auto <url>")
            sys.exit(1)
        url = sys.argv[2]
        setup.auto_detect(url, save_to_csv=True)

    elif command == "config":
        if len(sys.argv) < 4:
            print("Error: URL and site name required")
            print("Usage: python setup_site.py config <url> <site_name>")
            sys.exit(1)
        url = sys.argv[2]
        site_name = sys.argv[3]
        setup.create_custom_config(url, site_name)

    else:
        print(f"Unknown command: {command}")
        print("Use 'python setup_site.py' for help")
        sys.exit(1)


if __name__ == "__main__":
    main()
