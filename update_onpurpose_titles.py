#!/usr/bin/env python3
"""
Update existing OnPurpose Careers job titles by extracting from URLs.
Improves feed quality by replacing generic "Apply Now" titles with actual job titles.
"""

import sqlite3
from scraper import JobScraper


def update_onpurpose_titles():
    """Update all OnPurpose Careers job titles using URL extraction"""

    scraper = JobScraper()

    # Get all OnPurpose jobs with generic titles
    generic_titles = ['Apply Now', 'Job Board', 'Resources', 'Find a Career Coach',
                     'Give the Gift of Career Support', 'Post a Job', 'Apply', 'View Job']

    placeholders = ','.join('?' * len(generic_titles))

    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT id, title, url
            FROM jobs
            WHERE site_name = 'OnPurpose Careers'
            AND title IN ({placeholders})
        """, generic_titles)

        jobs_to_update = cursor.fetchall()

        print(f'Found {len(jobs_to_update)} OnPurpose jobs with generic titles')
        print('Extracting titles from URLs...\n')

        updated_count = 0
        kept_count = 0

        for job_id, old_title, url in jobs_to_update:
            extracted_title = scraper._extract_title_from_url(url)

            if extracted_title and extracted_title != old_title:
                cursor.execute("""
                    UPDATE jobs
                    SET title = ?
                    WHERE id = ?
                """, (extracted_title, job_id))

                updated_count += 1
                if updated_count <= 10:  # Show first 10 updates
                    print(f'Updated: "{old_title}" -> "{extracted_title}"')
                    print(f'  URL: {url[:80]}...' if len(url) > 80 else f'  URL: {url}')
                    print()
            else:
                kept_count += 1

        conn.commit()

    print(f'\nSummary:')
    print(f'  Updated: {updated_count} jobs')
    print(f'  Kept original: {kept_count} jobs')
    print(f'  Total processed: {len(jobs_to_update)} jobs')
    print(f'  Success rate: {updated_count * 100 // len(jobs_to_update) if jobs_to_update else 0}%')


if __name__ == '__main__':
    update_onpurpose_titles()
