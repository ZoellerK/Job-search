#!/usr/bin/env python3
"""
URL Validator and Improver for Job Sites
Validates URLs in sites.csv and searches for better ATS links
"""

import csv
import requests
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse
import re


class SiteValidator:
    """Validates and improves career site URLs"""

    # Common ATS platforms to search for
    ATS_PATTERNS = {
        'greenhouse': r'greenhouse\.io',
        'lever': r'lever\.co',
        'workable': r'workable\.com',
        'jobvite': r'jobvite\.com',
        'icims': r'icims\.com',
        'workday': r'myworkdayjobs\.com',
        'breezy': r'breezy\.hr',
        'bamboohr': r'bamboohr\.com',
        'paylocity': r'paylocity\.com',
        'teamtailor': r'teamtailor\.com',
        'applytojob': r'applytojob\.com',
        'ultipro': r'ultipro\.com',
        'adp': r'adp\.com.*recruitment',
        'taleo': r'taleo\.net',
    }

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def validate_url(self, url: str, site_name: str) -> Dict:
        """
        Validate a URL and check for issues

        Returns:
            Dict with: {
                'url': str,
                'site_name': str,
                'status': 'ok' | 'redirect' | 'error' | '404',
                'status_code': int,
                'final_url': str,
                'has_ats': bool,
                'ats_platform': str or None,
                'message': str
            }
        """
        result = {
            'url': url,
            'site_name': site_name,
            'status': 'unknown',
            'status_code': None,
            'final_url': url,
            'has_ats': False,
            'ats_platform': None,
            'message': ''
        }

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            result['status_code'] = response.status_code
            result['final_url'] = response.url

            # Check status
            if response.status_code == 404:
                result['status'] = '404'
                result['message'] = 'Page not found'
            elif response.status_code >= 400:
                result['status'] = 'error'
                result['message'] = f'HTTP {response.status_code}'
            elif response.url != url:
                result['status'] = 'redirect'
                result['message'] = f'Redirects to: {response.url}'
            else:
                result['status'] = 'ok'
                result['message'] = 'URL is valid'

            # Check if it's already an ATS URL
            for platform, pattern in self.ATS_PATTERNS.items():
                if re.search(pattern, response.url, re.IGNORECASE):
                    result['has_ats'] = True
                    result['ats_platform'] = platform
                    break

            # Look for ATS links in page content
            if not result['has_ats'] and response.status_code == 200:
                better_url = self._find_ats_link(response.text, url)
                if better_url:
                    result['better_url'] = better_url
                    result['message'] += f' | Better ATS URL found: {better_url}'

        except requests.exceptions.Timeout:
            result['status'] = 'error'
            result['message'] = 'Request timeout'
        except requests.exceptions.ConnectionError:
            result['status'] = 'error'
            result['message'] = 'Connection error'
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f'Error: {str(e)[:100]}'

        return result

    def _find_ats_link(self, html: str, base_url: str) -> Optional[str]:
        """Search HTML for ATS platform links"""
        # Look for common ATS URLs in the HTML
        for platform, pattern in self.ATS_PATTERNS.items():
            # Find URLs matching the pattern
            matches = re.findall(r'https?://[^\s<>"\']+' + pattern + r'[^\s<>"\']*', html, re.IGNORECASE)
            if matches:
                # Return the first match that looks like a jobs/careers page
                for match in matches:
                    if any(word in match.lower() for word in ['job', 'career', 'apply', 'opening']):
                        return match

        return None

    def validate_all_sites(self, sites_file: str = 'sites.csv') -> List[Dict]:
        """Validate all sites in the CSV file"""
        results = []

        try:
            with open(sites_file, 'r') as f:
                reader = csv.DictReader(f)
                sites = list(reader)
        except FileNotFoundError:
            print(f"Error: {sites_file} not found")
            return []

        print(f"\n{'='*80}")
        print(f"Validating {len(sites)} sites...")
        print(f"{'='*80}\n")

        for i, site in enumerate(sites, 1):
            site_name = site.get('site_name', 'Unknown')
            url = site.get('url', '')
            active = site.get('active', '').lower() in ['yes', 'true', '1']

            if not active:
                print(f"[{i}/{len(sites)}] Skipping {site_name} (inactive)")
                continue

            print(f"[{i}/{len(sites)}] Checking {site_name}...")
            print(f"            {url}")

            result = self.validate_url(url, site_name)
            results.append(result)

            # Print status
            status_emoji = {
                'ok': '✅',
                'redirect': '🔄',
                '404': '❌',
                'error': '⚠️'
            }.get(result['status'], '❓')

            print(f"            {status_emoji} {result['message']}")

            if result.get('has_ats'):
                print(f"            🎯 Already using {result['ats_platform'].upper()}")

            if result.get('better_url'):
                print(f"            💡 Suggested: {result['better_url']}")

            print()

            # Rate limiting
            time.sleep(0.5)

        return results

    def generate_report(self, results: List[Dict], output_file: str = 'validation_report.txt'):
        """Generate a detailed validation report"""

        # Categorize results
        ok = [r for r in results if r['status'] == 'ok']
        redirects = [r for r in results if r['status'] == 'redirect']
        errors = [r for r in results if r['status'] in ['404', 'error']]
        better_urls = [r for r in results if r.get('better_url')]

        report_lines = []
        report_lines.append("="*80)
        report_lines.append("SITE VALIDATION REPORT")
        report_lines.append("="*80)
        report_lines.append("")

        # Summary
        report_lines.append("SUMMARY")
        report_lines.append("-"*80)
        report_lines.append(f"Total sites checked: {len(results)}")
        report_lines.append(f"✅ Valid URLs: {len(ok)}")
        report_lines.append(f"🔄 Redirects: {len(redirects)}")
        report_lines.append(f"❌ Errors/404s: {len(errors)}")
        report_lines.append(f"💡 Better URLs found: {len(better_urls)}")
        report_lines.append("")

        # Errors section
        if errors:
            report_lines.append("="*80)
            report_lines.append("ERRORS AND 404s (NEEDS ATTENTION)")
            report_lines.append("="*80)
            for r in errors:
                report_lines.append(f"\n{r['site_name']}")
                report_lines.append(f"  Current URL: {r['url']}")
                report_lines.append(f"  Status: {r['status']} - {r['message']}")
                report_lines.append(f"  Action: NEEDS NEW URL")
            report_lines.append("")

        # Better URLs section
        if better_urls:
            report_lines.append("="*80)
            report_lines.append("BETTER ATS URLS FOUND")
            report_lines.append("="*80)
            for r in better_urls:
                report_lines.append(f"\n{r['site_name']}")
                report_lines.append(f"  Current URL: {r['url']}")
                report_lines.append(f"  Suggested URL: {r['better_url']}")
                report_lines.append(f"  Action: CONSIDER UPDATING")
            report_lines.append("")

        # Redirects section
        if redirects:
            report_lines.append("="*80)
            report_lines.append("REDIRECTS (MAY NEED UPDATING)")
            report_lines.append("="*80)
            for r in redirects:
                report_lines.append(f"\n{r['site_name']}")
                report_lines.append(f"  Current URL: {r['url']}")
                report_lines.append(f"  Redirects to: {r['final_url']}")
                if r.get('has_ats'):
                    report_lines.append(f"  Platform: {r['ats_platform'].upper()}")
                report_lines.append(f"  Action: CONSIDER UPDATING TO FINAL URL")
            report_lines.append("")

        # All OK section
        report_lines.append("="*80)
        report_lines.append("VALID URLS (NO ACTION NEEDED)")
        report_lines.append("="*80)
        for r in ok:
            ats_info = f" ({r['ats_platform'].upper()})" if r.get('has_ats') else ""
            report_lines.append(f"✅ {r['site_name']}{ats_info}")
        report_lines.append("")

        # Write to file
        report_text = '\n'.join(report_lines)
        with open(output_file, 'w') as f:
            f.write(report_text)

        # Also print summary to console
        print("\n" + "="*80)
        print("VALIDATION COMPLETE")
        print("="*80)
        print(f"✅ Valid URLs: {len(ok)}")
        print(f"🔄 Redirects: {len(redirects)}")
        print(f"❌ Errors/404s: {len(errors)}")
        print(f"💡 Better URLs found: {len(better_urls)}")
        print(f"\n📄 Full report saved to: {output_file}")
        print("="*80 + "\n")

        return output_file


def main():
    """Main entry point"""
    import sys

    validator = SiteValidator(timeout=15)

    sites_file = 'sites.csv'
    if len(sys.argv) > 1:
        sites_file = sys.argv[1]

    # Run validation
    results = validator.validate_all_sites(sites_file)

    # Generate report
    if results:
        validator.generate_report(results)


if __name__ == "__main__":
    main()
