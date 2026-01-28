import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Optional


class JobDatabase:
    """Manages job postings in SQLite database"""

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def _connect(self):
        """Context manager that guarantees connection cleanup"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    posted_date TEXT,
                    discovered_date TEXT NOT NULL,
                    keywords TEXT,
                    UNIQUE(url)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS site_parsers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_name TEXT UNIQUE NOT NULL,
                    url_pattern TEXT NOT NULL,
                    parser_config TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)

            conn.commit()

    def add_job(self, site_name: str, url: str, title: str,
                description: str = None, location: str = None,
                posted_date: str = None, keywords: str = None) -> bool:
        """
        Add a new job posting to the database
        Returns True if added, False if duplicate
        """
        with self._connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO jobs (site_name, url, title, description, location,
                                    posted_date, discovered_date, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (site_name, url, title, description, location, posted_date,
                      datetime.now(timezone.utc).isoformat(), keywords))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def _rows_to_jobs(self, rows) -> List[Dict]:
        """Convert database rows to job dictionaries"""
        return [{
            'id': row[0],
            'site_name': row[1],
            'url': row[2],
            'title': row[3],
            'description': row[4],
            'location': row[5],
            'posted_date': row[6],
            'discovered_date': row[7],
            'keywords': row[8]
        } for row in rows]

    def get_recent_jobs(self, limit: int = 100) -> List[Dict]:
        """Get most recently discovered jobs"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords
                FROM jobs
                ORDER BY discovered_date DESC
                LIMIT ?
            """, (limit,))

            return self._rows_to_jobs(cursor.fetchall())

    def get_new_jobs_since(self, since_date: str) -> List[Dict]:
        """Get jobs discovered since a specific date"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords
                FROM jobs
                WHERE discovered_date > ?
                ORDER BY discovered_date DESC
            """, (since_date,))

            return self._rows_to_jobs(cursor.fetchall())

    def job_exists(self, url: str) -> bool:
        """Check if a job URL already exists in database"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    def save_parser_config(self, site_name: str, url_pattern: str,
                          parser_config: Dict):
        """Save parser configuration for a site"""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO site_parsers
                (site_name, url_pattern, parser_config, last_updated)
                VALUES (?, ?, ?, ?)
            """, (site_name, url_pattern, json.dumps(parser_config),
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_parser_config(self, site_name: str) -> Optional[Dict]:
        """Get parser configuration for a site"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT parser_config FROM site_parsers WHERE site_name = ?
            """, (site_name,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM jobs")
            total_jobs = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM jobs
                WHERE date(discovered_date) = date('now')
            """)
            today_jobs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT site_name) FROM jobs")
            total_sites = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM jobs
                WHERE date(discovered_date) >= date('now', '-7 days')
            """)
            week_jobs = cursor.fetchone()[0]

            return {
                'total_jobs': total_jobs,
                'jobs_today': today_jobs,
                'jobs_this_week': week_jobs,
                'total_sites': total_sites
            }

    def cleanup_old_jobs(self, days_to_keep: int = 90) -> int:
        """
        Delete jobs older than specified days

        Args:
            days_to_keep: Number of days to keep jobs (default: 90)

        Returns:
            Number of jobs deleted
        """
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM jobs
                WHERE date(discovered_date) < date('now', '-' || ? || ' days')
            """, (days_to_keep,))

            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
