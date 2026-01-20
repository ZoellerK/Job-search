from feedgen.feed import FeedGenerator
from datetime import datetime
from typing import List, Dict
import pytz


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
        fg = FeedGenerator()
        fg.title(self.title)
        fg.description(self.description)
        fg.link(href=self.link, rel='self')
        fg.language('en')
        fg.author({'name': self.author})

        # Add each job as a feed entry
        for job in jobs:
            fe = fg.add_entry()

            # Required fields
            title = f"{job.get('title', 'Unknown Position')}"
            if job.get('site_name'):
                title += f" - {job['site_name']}"
            if job.get('location'):
                title += f" ({job['location']})"

            fe.title(title)
            fe.link(href=job.get('url', self.link))

            # Generate unique ID for the entry
            fe.id(job.get('url', f"job-{job.get('id', 'unknown')}"))

            # Description
            description = self._build_description(job)
            fe.description(description)

            # Publication date
            pub_date = self._parse_date(job.get('discovered_date') or job.get('posted_date'))
            if pub_date:
                fe.pubDate(pub_date)
            else:
                fe.pubDate(datetime.now(pytz.UTC))

            # Categories/keywords
            if job.get('keywords'):
                for keyword in job['keywords'].split(','):
                    fe.category(term=keyword.strip())

        # Write to file
        fg.rss_file(output_file, pretty=True)
        return output_file

    def _build_description(self, job: Dict) -> str:
        """Build HTML description for feed entry"""
        parts = []

        if job.get('description'):
            parts.append(f"<p>{job['description']}</p>")

        if job.get('location'):
            parts.append(f"<p><strong>Location:</strong> {job['location']}</p>")

        if job.get('site_name'):
            parts.append(f"<p><strong>Source:</strong> {job['site_name']}</p>")

        if job.get('keywords'):
            parts.append(f"<p><strong>Keywords:</strong> {job['keywords']}</p>")

        if job.get('posted_date'):
            parts.append(f"<p><strong>Posted:</strong> {job['posted_date']}</p>")

        if job.get('url'):
            parts.append(f"<p><a href=\"{job['url']}\">View Job Posting</a></p>")

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
