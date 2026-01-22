from datetime import datetime
from typing import List, Dict
import pytz
import xml.etree.ElementTree as ET
from xml.dom import minidom


class RSSFeedGenerator:
    """Generates RSS feed from job postings"""

    def __init__(self, title: str = "Job Postings", description: str = "Aggregated job postings",
                 link: str = "http://localhost:8000/feed.xml", author: str = "Job Search Tool",
                 include_site_in_title: bool = True, simple_descriptions: bool = False):
        self.title = title
        self.description = description
        self.link = link
        self.author = author
        self.include_site_in_title = include_site_in_title
        self.simple_descriptions = simple_descriptions

    def generate_feed(self, jobs: List[Dict], output_file: str = "feed.xml") -> str:
        """
        Generate RSS feed from job postings

        Args:
            jobs: List of job dictionaries with keys: title, url, description, etc.
            output_file: Path to save the RSS feed file

        Returns:
            Path to the generated feed file
        """
        # Create RSS root element
        rss = ET.Element('rss', version='2.0')
        channel = ET.SubElement(rss, 'channel')

        # Channel metadata
        ET.SubElement(channel, 'title').text = self.title
        ET.SubElement(channel, 'link').text = self.link
        ET.SubElement(channel, 'description').text = self.description
        ET.SubElement(channel, 'language').text = 'en'
        ET.SubElement(channel, 'lastBuildDate').text = self._format_rfc822_date(datetime.now(pytz.UTC))

        # Add each job as an item
        for job in jobs:
            item = ET.SubElement(channel, 'item')

            # Title - cleaner format
            title = f"{job.get('title', 'Unknown Position')}"

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
                source = ET.SubElement(item, 'source', url=job.get('url', self.link))
                source.text = job['site_name']

            # Author - use site name if available
            if job.get('site_name'):
                ET.SubElement(item, 'author').text = job['site_name']

            # Description - use simple or rich HTML based on preference
            if self.simple_descriptions:
                description = self._build_simple_description(job)
            else:
                description = self._build_description(job)
            ET.SubElement(item, 'description').text = description

            # Publication date - more robust handling
            pub_date = self._parse_date(job.get('discovered_date') or job.get('posted_date'))
            if pub_date:
                ET.SubElement(item, 'pubDate').text = self._format_rfc822_date(pub_date)
            # Skip pubDate if we don't have one rather than using "now"

            # Categories/keywords
            if job.get('keywords'):
                for keyword in job['keywords'].split(','):
                    ET.SubElement(item, 'category').text = keyword.strip()

            # Add site name as a category too for filtering
            if job.get('site_name'):
                ET.SubElement(item, 'category').text = job['site_name']

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

    def _build_simple_description(self, job: Dict) -> str:
        """Build simple plain-text description for feed readers that don't handle HTML well"""
        parts = []

        # Basic metadata
        if job.get('location'):
            parts.append(f"Location: {job['location']}")
        if job.get('site_name'):
            parts.append(f"Source: {job['site_name']}")
        if job.get('posted_date'):
            parts.append(f"Posted: {job['posted_date']}")

        if parts:
            parts.append("")  # Blank line

        # Description
        if job.get('description'):
            # Truncate if very long
            desc = job['description']
            if len(desc) > 500:
                desc = desc[:497] + "..."
            parts.append(desc)

        # URL
        if job.get('url'):
            parts.append(f"\nApply: {job['url']}")

        return '\n'.join(parts) if parts else "No description available"

    def _build_description(self, job: Dict) -> str:
        """Build enhanced HTML description for feed entry"""
        parts = []

        # Cleaner metadata section
        metadata = []
        if job.get('location'):
            metadata.append(f"<strong>Location:</strong> {job['location']}")
        if job.get('site_name'):
            metadata.append(f"<strong>Source:</strong> {job['site_name']}")
        if job.get('posted_date'):
            metadata.append(f"<strong>Posted:</strong> {job['posted_date']}")

        if metadata:
            parts.append(f"<div style='background: #f8f9fa; padding: 12px; margin-bottom: 16px; border-left: 4px solid #0066cc; font-size: 14px;'>{' &nbsp;|&nbsp; '.join(metadata)}</div>")

        # Add full description with better formatting
        if job.get('description'):
            # Escape HTML entities and preserve line breaks
            desc = job['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            # Convert double line breaks to paragraphs
            paragraphs = desc.split('\n\n')
            if len(paragraphs) > 1:
                desc = '</p><p>'.join(paragraphs)
                desc = f"<p>{desc}</p>"
            else:
                # Single paragraph - just convert line breaks
                desc = desc.replace('\n', '<br>')
                desc = f"<p>{desc}</p>"

            parts.append(f"<div style='margin: 16px 0; line-height: 1.6;'>{desc}</div>")

        # Keywords as tags
        if job.get('keywords'):
            keywords_list = [f"<span style='background: #e8f4f8; color: #0066cc; padding: 4px 10px; border-radius: 12px; margin-right: 6px; font-size: 13px; display: inline-block; margin-bottom: 4px;'>{kw.strip()}</span>"
                           for kw in job['keywords'].split(',')]
            parts.append(f"<div style='margin: 20px 0;'><strong>Tags:</strong><br/><div style='margin-top: 8px;'>{''.join(keywords_list)}</div></div>")

        # Prominent call-to-action button
        if job.get('url'):
            parts.append(f"<div style='margin-top: 24px; padding-top: 16px; border-top: 1px solid #e0e0e0;'><a href=\"{job['url']}\" style='background: #0066cc; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;'>→ Apply Now</a></div>")

        return '\n'.join(parts) if parts else "No description available"

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        try:
            # Try ISO format first
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        except (ValueError, AttributeError):
            # Return current time if parsing fails
            return datetime.now(pytz.UTC)

    def _format_rfc822_date(self, dt: datetime) -> str:
        """Format datetime as RFC 822 date string for RSS"""
        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
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
            title = job.get('title', 'Unknown Position')
            url = job.get('url', '#')
            site = job.get('site_name', 'Unknown Source')
            location = job.get('location', 'Location not specified')
            description = job.get('description', 'No description available')
            discovered = job.get('discovered_date', 'Unknown')

            html_parts.extend([
                "<div class='job'>",
                f"<h2><a href='{url}' target='_blank'>{title}</a></h2>",
                f"<div class='meta'>",
                f"<strong>Source:</strong> {site} | ",
                f"<strong>Location:</strong> {location} | ",
                f"<strong>Discovered:</strong> {discovered}",
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
