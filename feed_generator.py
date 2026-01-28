from datetime import datetime
from typing import List, Dict
import pytz
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html


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
        ET.SubElement(channel, 'lastBuildDate').text = self._format_rfc822_date(datetime.now(pytz.UTC))

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

        # Combine title, description, and location for text analysis
        # Use 'or' to handle None values (job.get() returns None if key exists with None value)
        search_text = ' '.join([
            (job.get('title') or '').lower(),
            (job.get('description') or '').lower(),
            (job.get('location') or '').lower()
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

        return categories

    def _build_plain_summary(self, job: Dict) -> str:
        """Build plain text summary for Feedly preview cards (50-150 chars ideal)"""
        parts = []

        # Quick metadata line
        metadata_parts = []
        if job.get('location'):
            metadata_parts.append(job['location'])
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
        if job.get('posted_date'):
            metadata.append(f"📅 Posted {job['posted_date']}")

        if metadata:
            # Modern card-style header
            parts.append(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 20px;
                        margin: -10px -10px 20px -10px;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                <div style='font-size: 15px; opacity: 0.95;'>{' &nbsp;&nbsp;|&nbsp;&nbsp; '.join(metadata)}</div>
            </div>
            """)

        # Main description with better readability
        if job.get('description'):
            desc = job['description']

            desc = html.escape(desc)

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
                            formatted_paras.append(f"<p style='line-height: 1.7; margin-bottom: 16px; color: #333;'>{para.replace(chr(10), '<br>')}</p>")
                desc = ''.join(formatted_paras)
            else:
                desc = desc.replace('\n', '<br>')
                desc = f"<p style='line-height: 1.7; color: #333;'>{desc}</p>"

            parts.append(f"<div style='font-size: 15px;'>{desc}</div>")

        # Keywords/tags as visual pills
        if job.get('keywords'):
            keywords_html = []
            for kw in job['keywords'].split(','):
                kw = kw.strip()
                keywords_html.append(f"""
                    <span style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                 color: white;
                                 padding: 6px 14px;
                                 border-radius: 20px;
                                 margin-right: 8px;
                                 margin-bottom: 8px;
                                 font-size: 13px;
                                 display: inline-block;
                                 font-weight: 500;
                                 box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>{kw}</span>
                """)
            parts.append(f"""
                <div style='margin: 28px 0 24px 0; padding-top: 20px; border-top: 2px solid #f0f0f0;'>
                    <div style='color: #666; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600;'>Tags</div>
                    <div>{''.join(keywords_html)}</div>
                </div>
            """)

        # Prominent CTA button (Feedly renders this beautifully)
        if job.get('url'):
            parts.append(f"""
                <div style='margin-top: 32px; text-align: center; padding: 24px; background: #f8f9fa; border-radius: 8px;'>
                    <a href="{job['url']}"
                       style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                              color: white;
                              padding: 14px 32px;
                              text-decoration: none;
                              border-radius: 6px;
                              display: inline-block;
                              font-weight: 600;
                              font-size: 16px;
                              box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                              transition: all 0.3s;'>
                        🚀 Apply for this Position
                    </a>
                </div>
            """)

        return ''.join(parts) if parts else "No details available"

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
            return None

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
            title = html.escape(job.get('title', 'Unknown Position'))
            url = html.escape(job.get('url', '#'))
            site = html.escape(job.get('site_name', 'Unknown Source'))
            location = html.escape(job.get('location', 'Location not specified'))
            description = html.escape(job.get('description', 'No description available'))
            discovered = html.escape(job.get('discovered_date', 'Unknown'))

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
