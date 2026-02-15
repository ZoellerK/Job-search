#!/usr/bin/env python3
"""
Simple script to regenerate the RSS feed from current database
"""

import json
from database import JobDatabase
from feed_generator import RSSFeedGenerator


def main():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)

    # Initialize database and feed generator using config values
    db = JobDatabase(config['database']['path'])
    feed_gen = RSSFeedGenerator(
        title=config['feed']['title'],
        description=config['feed']['description'],
        link=config['feed']['link'],
        author=config['feed']['author'],
        include_site_in_title=config['feed'].get('include_site_in_title', True),
        simple_descriptions=config['feed'].get('simple_descriptions', False)
    )

    # Get recent jobs
    print("Fetching jobs from database...")
    jobs = db.get_recent_jobs(limit=config['output']['max_items'])
    print(f"Found {len(jobs)} jobs")

    # Generate feed
    print("\nGenerating feed...")
    feed_gen.generate_feed(jobs, config['output']['feed_file'])
    print(f"Feed generated: {config['output']['feed_file']}")

    # Generate preview
    print("\nGenerating preview...")
    feed_gen.generate_html_preview(jobs, "preview.html")
    print("Preview generated: preview.html")


if __name__ == "__main__":
    main()
