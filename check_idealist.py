#!/usr/bin/env python3
"""Check Idealist jobs in database"""
import sqlite3


def main():
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()

        # Check total jobs
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE site_name = 'Idealist'")
        idealist_count = cursor.fetchone()[0]
        print(f"Idealist jobs in database: {idealist_count}")

        # Check all jobs
        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_count = cursor.fetchone()[0]
        print(f"Total jobs in database: {total_count}")

        # Get a sample of recent jobs
        cursor.execute("SELECT site_name, COUNT(*) as count FROM jobs GROUP BY site_name ORDER BY count DESC LIMIT 10")
        print("\nTop 10 sites by job count:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    main()
