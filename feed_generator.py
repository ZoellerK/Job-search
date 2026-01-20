from datetime import datetime
from typing import List, Dict
import pytz
import xml.etree.ElementTree as ET
from xml.dom import minidom


class RSSFeedGenerator:
    """Generates RSS feed from job postings"""

    def __init__(self, title: str = "Job Postings", description: str = "Aggregated job postings",
                 link: str = "http://localhost:8000/feed.xml", author: str = "Job Search Tool"):
        self.title = title
        self.description = description
        self.link = link
        self.author = author

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

            # Title
            title = f"{job.get('title', 'Unknown Position')}"
            if job.get('site_name'):
                title += f" - {job['site_name']}"
            if job.get('location'):
                title += f" ({job['location']})"
            ET.SubElement(item, 'title').text = title

            # Link
            job_url = job.get('url', self.link)
            ET.SubElement(item, 'link').text = job_url
            ET.SubElement(item, 'guid', isPermaLink='true').text = job_url

            # Description
            description = self._build_description(job)
            ET.SubElement(item, 'description').text = description

            # Publication date
            pub_date = self._parse_date(job.get('discovered_date') or job.get('posted_date'))
            if pub_date:
                ET.SubElement(item, 'pubDate').text = self._format_rfc822_date(pub_date)
            else:
                ET.SubElement(item, 'pubDate').text = self._format_rfc822_date(datetime.now(pytz.UTC))

            # Categories/keywords
            if job.get('keywords'):
                for keyword in job['keywords'].split(','):
                    ET.SubElement(item, 'category').text = keyword.strip()

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

    def _build_description(self, job: Dict) -> str:
        """Build HTML description for feed entry"""
        parts = []

        # Add metadata box at the top
        metadata = []
        if job.get('location'):
            metadata.append(f"📍 <strong>{job['location']}</strong>")
        if job.get('site_name'):
            metadata.append(f"🏢 {job['site_name']}")
        if job.get('posted_date'):
            metadata.append(f"📅 {job['posted_date']}")

        if metadata:
            parts.append(f"<div style='background: #f0f0f0; padding: 10px; margin-bottom: 15px; border-radius: 5px;'>{' | '.join(metadata)}</div>")

        # Add full description
        if job.get('description'):
            # Escape HTML entities and preserve line breaks
            desc = job['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Make description more readable with paragraphs
            desc = desc.replace('\n', '<br>')
            parts.append(f"<div style='margin: 15px 0;'>{desc}</div>")

        # Add keywords if present
        if job.get('keywords'):
            keywords_list = [f"<span style='background: #e3f2fd; padding: 2px 8px; border-radius: 3px; margin-right: 5px;'>{kw.strip()}</span>"
                           for kw in job['keywords'].split(',')]
            parts.append(f"<div style='margin: 15px 0;'><strong>🔍 Keywords:</strong> {''.join(keywords_list)}</div>")

        # Add link to full posting
        if job.get('url'):
            parts.append(f"<div style='margin-top: 20px;'><a href=\"{job['url']}\" style='background: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;'>→ View Full Job Posting</a></div>")

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
