#!/usr/bin/env python3
"""
Simple script to regenerate the RSS feed from current database
"""

import json
from database import JobDatabase
from feed_generator import RSSFeedGenerator

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize database and feed generator
db = JobDatabase()
feed_gen = RSSFeedGenerator(
    title=config['feed']['title'],
    description="RSS feed of job postings aggregated from multiple sources - optimized for Feedly",
    link="https://zoellerk.github.io/Job-search/feed.xml",
    author="Job Search Tool",
    include_site_in_title=config['feed']['include_site_in_title'],
    simple_descriptions=config['feed']['simple_descriptions']
)

# Get recent jobs
print("Fetching jobs from database...")
jobs = db.get_recent_jobs(limit=config['output']['max_items'])
print(f"Found {len(jobs)} jobs")

# Show sample OnPurpose jobs
onpurpose_jobs = [j for j in jobs if j.get('site_name') == 'OnPurpose Careers']
print(f"\nSample OnPurpose job titles (first 10):")
for job in onpurpose_jobs[:10]:
    print(f"  - {job['title']}")

# Generate feed
print("\nGenerating feed...")
feed_gen.generate_feed(jobs, config['output']['feed_file'])
print(f"✓ Feed generated: {config['output']['feed_file']}")

# Generate preview
print("\nGenerating preview...")
feed_gen.generate_html_preview(jobs, "preview.html")
print("✓ Preview generated: preview.html")
