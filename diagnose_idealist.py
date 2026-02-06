#!/usr/bin/env python3
"""
Diagnostic script for Idealist scraper.
Run this locally (not in Claude Code) to see what the page structure actually is.
"""
import requests
from bs4 import BeautifulSoup
import re

def diagnose_idealist():
    """Analyze Idealist page structure to debug scraper"""

    # Test both URLs
    urls_to_test = [
        "https://www.idealist.org/en/jobs",
        "https://www.idealist.org/en/nonprofit-jobs"
    ]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for url in urls_to_test:
        print("=" * 80)
        print(f"TESTING: {url}")
        print("=" * 80)

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            print(f"✓ Page loaded successfully")
            print(f"  Status: {response.status_code}")
            print(f"  Title: {soup.title.string if soup.title else 'No title'}")

            # Find all links
            all_links = soup.find_all('a', href=True)
            print(f"\n  Total links: {len(all_links)}")

            # Analyze link patterns
            url_patterns = {}
            for link in all_links:
                href = link['href']
                # Extract pattern
                if '/en/' in href:
                    # Get the part after /en/
                    parts = href.split('/en/')
                    if len(parts) > 1:
                        pattern_parts = parts[1].split('/')[:2]  # First 2 segments
                        pattern = '/en/' + '/'.join(pattern_parts)
                        url_patterns[pattern] = url_patterns.get(pattern, 0) + 1

            print(f"\n  Top URL patterns found:")
            sorted_patterns = sorted(url_patterns.items(), key=lambda x: x[1], reverse=True)
            for pattern, count in sorted_patterns[:15]:
                print(f"    {pattern}: {count} links")

            # Look for job-specific patterns
            print(f"\n  Job-related link patterns:")
            job_patterns = [
                r'/en/nonprofit-job/',
                r'/en/nonprofit-jobs',
                r'/en/jobs/',
                r'/en/job/',
            ]

            for pattern in job_patterns:
                matching_links = [l for l in all_links if re.search(pattern, l['href'])]
                print(f"    Links matching '{pattern}': {len(matching_links)}")
                if matching_links:
                    # Show first 3 examples
                    print(f"      Examples:")
                    for link in matching_links[:3]:
                        title = link.get_text(strip=True)[:60]
                        href = link['href'][:80]
                        print(f"        - {title}")
                        print(f"          {href}")

            # Check if page uses JavaScript rendering
            script_tags = soup.find_all('script')
            print(f"\n  Script tags: {len(script_tags)}")

            # Look for common JS frameworks
            frameworks_found = []
            for script in script_tags:
                src = script.get('src', '')
                if 'react' in src.lower():
                    frameworks_found.append('React')
                if 'vue' in src.lower():
                    frameworks_found.append('Vue')
                if 'angular' in src.lower():
                    frameworks_found.append('Angular')

            if frameworks_found:
                print(f"  ⚠️  JavaScript frameworks detected: {', '.join(set(frameworks_found))}")
                print(f"      This page might need JavaScript rendering!")

            # Look for data attributes or JSON that might contain jobs
            json_scripts = soup.find_all('script', type='application/json')
            if json_scripts:
                print(f"  Found {len(json_scripts)} JSON script tags (might contain job data)")

            print()

        except Exception as e:
            print(f"✗ Error loading {url}: {e}")
            print()

if __name__ == "__main__":
    print("Idealist Scraper Diagnostic Tool")
    print("=" * 80)
    print()
    diagnose_idealist()
    print("=" * 80)
    print("RECOMMENDATION:")
    print("Based on the output above:")
    print("1. If you see many '/en/nonprofit-job/' links, the current config is correct")
    print("2. If you see a different pattern, update the url_pattern in sites.csv")
    print("3. If JavaScript frameworks are detected, consider using Selenium/Playwright")
