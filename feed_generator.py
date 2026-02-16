import logging
from datetime import datetime, timezone
from typing import List, Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html

logger = logging.getLogger(__name__)


class RSSFeedGenerator:
    """Generates RSS feed from job postings"""

    # Default relevance keywords — can be overridden via config
    DEFAULT_RELEVANCE_KEYWORDS = {
        'high': [
            'program', 'policy', 'grants', 'advocacy', 'strategy',
            'research', 'philanthropy', 'director', 'manager', 'officer',
        ],
        'medium': [
            'communications', 'partnerships', 'development', 'coordinator',
            'analyst', 'associate', 'operations', 'engagement', 'community',
        ],
    }

    def __init__(self, title: str = "Job Postings", description: str = "Aggregated job postings",
                 link: str = "http://localhost:8000/feed.xml", author: str = "Job Search Tool",
                 include_site_in_title: bool = True, simple_descriptions: bool = False,
                 relevance_keywords: Dict = None):
        self.title = title
        self.description = description
        self.link = link
        self.author = author
        self.include_site_in_title = include_site_in_title
        self.simple_descriptions = simple_descriptions
        self.relevance_keywords = relevance_keywords or self.DEFAULT_RELEVANCE_KEYWORDS

    def generate_feed(self, jobs: List[Dict], output_file: str = "feed.xml") -> str:
        """
        Generate RSS feed from job postings optimized for Feedly

        Args:
            jobs: List of job dictionaries with keys: title, url, description, etc.
            output_file: Path to save the RSS feed file

        Returns:
            Path to the generated feed file
        """
        # Register namespaces FIRST to ensure proper prefixes
        ET.register_namespace('content', 'http://purl.org/rss/1.0/modules/content/')
        ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
        ET.register_namespace('media', 'http://search.yahoo.com/mrss/')
        ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')

        # Create RSS root element with namespaces for enhanced Feedly support
        rss = ET.Element('rss')
        rss.set('version', '2.0')

        channel = ET.SubElement(rss, 'channel')

        # Channel metadata - optimized for Feedly discovery
        ET.SubElement(channel, 'title').text = self.title
        ET.SubElement(channel, 'link').text = self.link
        ET.SubElement(channel, 'description').text = self.description
        ET.SubElement(channel, 'language').text = 'en'
        ET.SubElement(channel, 'lastBuildDate').text = self._format_rfc822_date(datetime.now(timezone.utc))

        # Add atom:link for better feed discovery (Feedly best practice)
        ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', {
            'href': self.link,
            'rel': 'self',
            'type': 'application/rss+xml'
        })

        # Add each job as an item
        for job in jobs:
            item = ET.SubElement(channel, 'item')

            # Title - cleaner format
            title = job.get('title', 'Unknown Position')

            # Only add site name if configured to do so
            if self.include_site_in_title and job.get('site_name'):
                title += f" - {job['site_name']}"

            # Add location to title if available
            if job.get('location'):
                title += f" ({job['location']})"
            ET.SubElement(item, 'title').text = title

            # Link
            job_url = job.get('url', self.link)
            ET.SubElement(item, 'link').text = job_url
            ET.SubElement(item, 'guid', isPermaLink='true').text = job_url

            # Source - separate element for better RSS reader support
            if job.get('site_name'):
                source = ET.SubElement(item, 'source', url=self.link)
                source.text = job['site_name']

            # Author - use site name if available
            if job.get('site_name'):
                ET.SubElement(item, 'author').text = job['site_name']
                # Add Dublin Core creator for better Feedly attribution
                ET.SubElement(item, '{http://purl.org/dc/elements/1.1/}creator').text = job['site_name']

            # Description - plain text summary for Feedly preview cards
            plain_summary = self._build_plain_summary(job)
            ET.SubElement(item, 'description').text = plain_summary

            # Content:encoded - rich HTML for Feedly article view (preferred by Feedly)
            if not self.simple_descriptions:
                rich_content = self._build_feedly_content(job)
                content_elem = ET.SubElement(item, '{http://purl.org/rss/1.0/modules/content/}encoded')
                content_elem.text = rich_content

            # Publication date - more robust handling
            pub_date = self._parse_date(job.get('discovered_date') or job.get('posted_date'))
            if pub_date:
                ET.SubElement(item, 'pubDate').text = self._format_rfc822_date(pub_date)
            # Skip pubDate if we don't have one rather than using "now"

            # Categories/keywords - extract smart metadata for Feedly filtering
            if job.get('keywords'):
                for keyword in job['keywords'].split(','):
                    ET.SubElement(item, 'category').text = keyword.strip()

            # Add site name as a category too for filtering
            if job.get('site_name'):
                ET.SubElement(item, 'category').text = job['site_name']

            # Extract job metadata for better categorization (Feedly filters)
            job_metadata = self._extract_job_metadata(job)
            for meta_category in job_metadata:
                ET.SubElement(item, 'category').text = meta_category

        # Convert to pretty XML string
        xml_str = self._prettify_xml(rss)

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        return output_file

    def _prettify_xml(self, elem):
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

    def _extract_job_metadata(self, job: Dict) -> List[str]:
        """Extract smart metadata from job for better Feedly categorization"""
        categories = []

        # Combine title, description, location, and job_type for text analysis
        # Use 'or' to handle None values (job.get() returns None if key exists with None value)
        search_text = ' '.join([
            (job.get('title') or '').lower(),
            (job.get('description') or '').lower(),
            (job.get('location') or '').lower(),
            (job.get('job_type') or '').lower()
        ])

        # Work arrangement
        if any(term in search_text for term in ['remote', 'work from home', 'wfh', 'telecommute']):
            categories.append('Remote')
        if any(term in search_text for term in ['hybrid', 'flexible']):
            categories.append('Hybrid')
        if any(term in search_text for term in ['on-site', 'onsite', 'in-office', 'office-based']):
            categories.append('On-site')

        # Employment type
        if any(term in search_text for term in ['full-time', 'full time', 'fulltime']):
            categories.append('Full-time')
        if any(term in search_text for term in ['part-time', 'part time', 'parttime']):
            categories.append('Part-time')
        if any(term in search_text for term in ['contract', 'contractor']):
            categories.append('Contract')
        if any(term in search_text for term in ['internship', 'intern']):
            categories.append('Internship')
        if any(term in search_text for term in ['volunteer']):
            categories.append('Volunteer')

        # Seniority level
        if any(term in search_text for term in ['senior', 'sr.', 'lead', 'principal', 'staff']):
            categories.append('Senior')
        if any(term in search_text for term in ['junior', 'jr.', 'entry level', 'entry-level']):
            categories.append('Junior')
        if any(term in search_text for term in ['director', 'vp', 'vice president', 'head of', 'chief']):
            categories.append('Leadership')

        # Relevance scoring
        relevance = self._score_relevance(job)
        if relevance:
            categories.append(relevance)

        return categories

    def _score_relevance(self, job: Dict) -> str:
        """Score job relevance based on keyword matches. Returns category string or empty."""
        search_text = ' '.join([
            (job.get('title') or '').lower(),
            (job.get('description') or '')[:500].lower(),
        ])
        if not search_text.strip():
            return ''

        # Count matches per tier
        high_matches = sum(1 for kw in self.relevance_keywords.get('high', [])
                          if kw.lower() in search_text)
        medium_matches = sum(1 for kw in self.relevance_keywords.get('medium', [])
                            if kw.lower() in search_text)

        if high_matches >= 2:
            return 'Relevance: High'
        if high_matches >= 1 or medium_matches >= 2:
            return 'Relevance: Medium'
        return ''

    def _build_plain_summary(self, job: Dict) -> str:
        """Build plain text summary for Feedly preview cards (50-150 chars ideal)"""
        parts = []

        # Quick metadata line
        metadata_parts = []
        if job.get('location'):
            metadata_parts.append(job['location'])
        if job.get('job_type'):
            metadata_parts.append(job['job_type'])
        if job.get('salary'):
            metadata_parts.append(job['salary'])
        if job.get('site_name'):
            metadata_parts.append(job['site_name'])

        if metadata_parts:
            parts.append(' • '.join(metadata_parts))

        # Truncated description for preview
        if job.get('description'):
            desc = job['description'].strip()
            # Remove excessive whitespace
            desc = ' '.join(desc.split())
            # Truncate for card preview (Feedly shows ~150 chars)
            if len(desc) > 200:
                desc = desc[:197] + '...'
            parts.append(desc)

        return '\n\n'.join(parts) if parts else "View job details"

    def _build_feedly_content(self, job: Dict) -> str:
        """Build rich HTML content optimized for Feedly article view"""
        parts = []

        # Header with emoji icons for visual hierarchy
        metadata = []
        if job.get('location'):
            # Use emoji for quick visual scanning
            metadata.append(f"📍 <strong>{job['location']}</strong>")
        if job.get('site_name'):
            metadata.append(f"🏢 {job['site_name']}")
        if job.get('job_type'):
            metadata.append(f"💼 {job['job_type']}")
        if job.get('salary'):
            metadata.append(f"💰 {job['salary']}")
        if job.get('posted_date'):
            metadata.append(f"📅 Posted {job['posted_date']}")

        if metadata:
            parts.append(f"<div style='background: #667eea; color: white; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; font-size: 14px;'>{' | '.join(metadata)}</div>")

        # Main description with better readability
        if job.get('description'):
            desc = html.escape(job['description'])

            # Convert paragraphs
            paragraphs = desc.split('\n\n')
            if len(paragraphs) > 1:
                formatted_paras = []
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        # Check if it looks like a heading (short, no punctuation at end)
                        if len(para) < 60 and not para.endswith('.') and not para.endswith(','):
                            formatted_paras.append(f"<h3 style='color: #667eea; margin-top: 24px; margin-bottom: 12px; font-size: 18px;'>{para}</h3>")
                        else:
                            para_content = para.replace(chr(10), '<br>')
                            formatted_paras.append(f"<p style='line-height: 1.7; margin-bottom: 16px; color: #333;'>{para_content}</p>")
                desc = ''.join(formatted_paras)
            else:
                desc = desc.replace('\n', '<br>')
                desc = f"<p style='line-height: 1.7; color: #333;'>{desc}</p>"

            parts.append(f"<div style='font-size: 15px;'>{desc}</div>")

        if job.get('keywords'):
            keywords_html = [
                f"<span style='background: #f0e6ff; color: #667eea; padding: 4px 12px; border-radius: 12px; font-size: 13px; display: inline-block; margin-right: 6px; margin-bottom: 4px;'>{kw.strip()}</span>"
                for kw in job['keywords'].split(',')
            ]
            parts.append(f"<div style='margin: 20px 0; padding-top: 16px; border-top: 1px solid #eee;'><strong style='color: #666; font-size: 13px;'>Tags</strong><br style='margin-bottom: 8px;'>{''.join(keywords_html)}</div>")

        if job.get('url'):
            safe_url = html.escape(job['url'])
            parts.append(f"<div style='margin-top: 24px; text-align: center; padding: 16px; background: #f8f9fa; border-radius: 4px;'><a href=\"{safe_url}\" style='background: #667eea; color: white; padding: 10px 24px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: 600;'>Apply for this Position</a></div>")

        return ''.join(parts) if parts else "No details available"

    def build_summary_item(self, scrape_results: Dict,
                           health_alerts: List[Dict] = None,
                           stale_count: int = 0) -> Dict:
        """Build a summary feed item from scraping results + health alerts."""
        summary_parts = []
        summary_parts.append("<h3>Update Summary</h3>")
        summary_parts.append(f"<p><strong>New Jobs Found:</strong> {scrape_results['total_new_jobs']}</p>")
        summary_parts.append(f"<p><strong>Sites Checked:</strong> {scrape_results['successful_sites']}/{scrape_results['successful_sites'] + scrape_results['failed_sites']}</p>")
        if stale_count:
            summary_parts.append(f"<p><strong>Stale Listings Hidden:</strong> {stale_count} (not seen in 30+ days)</p>")

        if scrape_results['failed_sites'] > 0:
            summary_parts.append(f"<p><strong>Failed Sites:</strong> {scrape_results['failed_sites']}</p>")
            failed_sites = [r['site_name'] for r in scrape_results['site_results'] if not r['success']]
            summary_parts.append(f"<p style='font-size: 0.9em; color: #666;'>{', '.join(failed_sites)}</p>")

        # Health alerts — persistently broken sites flagged for your attention
        if health_alerts:
            summary_parts.append(
                "<div style='background: #fff3cd; border: 1px solid #ffc107; "
                "padding: 12px 16px; border-radius: 4px; margin: 12px 0;'>"
            )
            summary_parts.append(
                "<strong style='color: #856404;'>Site Health Alerts</strong>"
                "<p style='color: #856404; margin: 4px 0;'>"
                "The following sites have failed 3+ consecutive scrapes and may need attention:</p><ul>"
            )
            for alert in health_alerts:
                name = html.escape(alert['site_name'])
                error = html.escape(alert.get('last_error') or 'unknown error')
                summary_parts.append(
                    f"<li><strong>{name}</strong> — {alert['consecutive_failures']} failures "
                    f"(last: {error})</li>"
                )
            summary_parts.append("</ul></div>")

        sites_with_jobs = [r for r in scrape_results['site_results'] if r['success'] and r['new_jobs'] > 0]
        if sites_with_jobs:
            summary_parts.append("<details><summary><strong>Sites with New Jobs</strong></summary>")
            summary_parts.append("<ul>")
            for result in sorted(sites_with_jobs, key=lambda x: x['new_jobs'], reverse=True):
                summary_parts.append(f"<li><strong>{result['site_name']}</strong>: {result['new_jobs']} new</li>")
            summary_parts.append("</ul></details>")

        title = f"Update - {scrape_results['total_new_jobs']} New Jobs Found"
        if health_alerts:
            title += f" ({len(health_alerts)} site alert{'s' if len(health_alerts) != 1 else ''})"

        return {
            'title': title,
            'url': self.link,
            'site_name': 'System Update',
            'description': '\n'.join(summary_parts),
            'discovered_date': datetime.now(timezone.utc).isoformat()
        }

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError):
            return None

    def _format_rfc822_date(self, dt: datetime) -> str:
        """Format datetime as RFC 822 date string for RSS"""
        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime('%a, %d %b %Y %H:%M:%S %z')

    def generate_html_preview(self, jobs: List[Dict], output_file: str = "preview.html") -> str:
        """
        Generate an HTML preview of job postings
        Useful for viewing in a browser
        """
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{self.title}</title>",
            "<meta charset='utf-8'>",
            "<style>",
            "body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            ".job { border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 5px; }",
            ".job h2 { margin-top: 0; color: #0066cc; }",
            ".job .meta { color: #666; font-size: 0.9em; }",
            ".job .description { margin: 10px 0; }",
            ".job a { color: #0066cc; text-decoration: none; }",
            ".job a:hover { text-decoration: underline; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{self.title}</h1>",
            f"<p>{self.description}</p>",
            f"<p><strong>Total Jobs:</strong> {len(jobs)}</p>",
            "<hr>"
        ]

        for job in jobs:
            title = html.escape(job.get('title') or 'Unknown Position')
            url = html.escape(job.get('url') or '#')
            site = html.escape(job.get('site_name') or 'Unknown Source')
            location = html.escape(job.get('location') or 'Location not specified')
            description = html.escape(job.get('description') or 'No description available')
            discovered = html.escape(job.get('discovered_date') or 'Unknown')
            job_type = html.escape(job.get('job_type') or '')
            salary = html.escape(job.get('salary') or '')

            # Build metadata line
            meta_parts = [f"<strong>Source:</strong> {site}"]
            if location and location != 'Location not specified':
                meta_parts.append(f"<strong>Location:</strong> {location}")
            if job_type:
                meta_parts.append(f"<strong>Type:</strong> {job_type}")
            if salary:
                meta_parts.append(f"<strong>Salary:</strong> {salary}")
            meta_parts.append(f"<strong>Discovered:</strong> {discovered}")

            html_parts.extend([
                "<div class='job'>",
                f"<h2><a href='{url}' target='_blank'>{title}</a></h2>",
                f"<div class='meta'>",
                ' | '.join(meta_parts),
                "</div>",
                f"<div class='description'>{description}</div>",
                f"<a href='{url}' target='_blank'>View Full Posting →</a>",
                "</div>"
            ])

        html_parts.extend([
            "</body>",
            "</html>"
        ])

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return output_file
