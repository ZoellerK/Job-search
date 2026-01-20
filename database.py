import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional


class JobDatabase:
    """Manages job postings in SQLite database"""

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

    def add_job(self, site_name: str, url: str, title: str,
                description: str = None, location: str = None,
                posted_date: str = None, keywords: str = None) -> bool:
        """
        Add a new job posting to the database
        Returns True if added, False if duplicate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO jobs (site_name, url, title, description, location,
                                posted_date, discovered_date, keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (site_name, url, title, description, location, posted_date,
                  datetime.now().isoformat(), keywords))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_recent_jobs(self, limit: int = 100) -> List[Dict]:
        """Get most recently discovered jobs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, site_name, url, title, description, location,
                   posted_date, discovered_date, keywords
            FROM jobs
            ORDER BY discovered_date DESC
            LIMIT ?
        """, (limit,))

        jobs = []
        for row in cursor.fetchall():
            jobs.append({
                'id': row[0],
                'site_name': row[1],
                'url': row[2],
                'title': row[3],
                'description': row[4],
                'location': row[5],
                'posted_date': row[6],
                'discovered_date': row[7],
                'keywords': row[8]
            })

        conn.close()
        return jobs

    def get_new_jobs_since(self, since_date: str) -> List[Dict]:
        """Get jobs discovered since a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, site_name, url, title, description, location,
                   posted_date, discovered_date, keywords
            FROM jobs
            WHERE discovered_date > ?
            ORDER BY discovered_date DESC
        """, (since_date,))

        jobs = []
        for row in cursor.fetchall():
            jobs.append({
                'id': row[0],
                'site_name': row[1],
                'url': row[2],
                'title': row[3],
                'description': row[4],
                'location': row[5],
                'posted_date': row[6],
                'discovered_date': row[7],
                'keywords': row[8]
            })

        conn.close()
        return jobs

    def job_exists(self, url: str) -> bool:
        """Check if a job URL already exists in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM jobs WHERE url = ?", (url,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def save_parser_config(self, site_name: str, url_pattern: str,
                          parser_config: Dict):
        """Save parser configuration for a site"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO site_parsers
            (site_name, url_pattern, parser_config, last_updated)
            VALUES (?, ?, ?, ?)
        """, (site_name, url_pattern, json.dumps(parser_config),
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def get_parser_config(self, site_name: str) -> Optional[Dict]:
        """Get parser configuration for a site"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT parser_config FROM site_parsers WHERE site_name = ?
        """, (site_name,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None

    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
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

        conn.close()

        return {
            'total_jobs': total_jobs,
            'jobs_today': today_jobs,
            'total_sites': total_sites
        }
