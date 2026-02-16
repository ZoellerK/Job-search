import sqlite3
import csv
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class JobDatabase:
    """Manages job postings in SQLite database"""

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def _connect(self):
        """Context manager that guarantees connection cleanup"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")

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
                    salary TEXT,
                    job_type TEXT,
                    details_scraped BOOLEAN DEFAULT 0,
                    last_seen_date TEXT,
                    stale BOOLEAN DEFAULT 0,
                    UNIQUE(url)
                )
            """)

            for col_def in [
                "salary TEXT",
                "job_type TEXT",
                "details_scraped BOOLEAN DEFAULT 0",
                "last_seen_date TEXT",
                "stale BOOLEAN DEFAULT 0",
            ]:
                try:
                    cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS site_parsers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_name TEXT UNIQUE NOT NULL,
                    url_pattern TEXT NOT NULL,
                    parser_config TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS site_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_name TEXT NOT NULL,
                    scrape_date TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    jobs_found INTEGER DEFAULT 0,
                    error_message TEXT,
                    http_status INTEGER
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_site_health_site_date
                ON site_health (site_name, scrape_date DESC)
            """)

            conn.commit()

    def add_job(self, site_name: str, url: str, title: str,
                description: str = None, location: str = None,
                posted_date: str = None, keywords: str = None,
                salary: str = None, job_type: str = None,
                details_scraped: bool = False) -> bool:
        """Add a new job posting. Returns True if added, False if duplicate."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO jobs (site_name, url, title, description, location,
                                    posted_date, discovered_date, keywords, salary,
                                    job_type, details_scraped, last_seen_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (site_name, url, title, description, location, posted_date,
                      now, keywords, salary,
                      job_type, details_scraped, now))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        return dict(row)

    def _rows_to_jobs(self, rows) -> List[Dict]:
        return [self._row_to_dict(row) for row in rows]

    def get_recent_jobs(self, limit: int = 100) -> List[Dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords, salary, job_type,
                       details_scraped, last_seen_date, stale
                FROM jobs
                ORDER BY discovered_date DESC
                LIMIT ?
            """, (limit,))
            return self._rows_to_jobs(cursor.fetchall())

    def get_new_jobs_since(self, since_date: str) -> List[Dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords, salary, job_type,
                       details_scraped, last_seen_date, stale
                FROM jobs
                WHERE discovered_date > ?
                ORDER BY discovered_date DESC
            """, (since_date,))
            return self._rows_to_jobs(cursor.fetchall())

    def update_job_details(self, url: str, description: str = None,
                          location: str = None, posted_date: str = None,
                          salary: str = None, job_type: str = None) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            updates = []
            values = []

            if description is not None:
                updates.append("description = ?")
                values.append(description)
            if location is not None:
                updates.append("location = ?")
                values.append(location)
            if posted_date is not None:
                updates.append("posted_date = ?")
                values.append(posted_date)
            if salary is not None:
                updates.append("salary = ?")
                values.append(salary)
            if job_type is not None:
                updates.append("job_type = ?")
                values.append(job_type)

            if updates:
                updates.append("details_scraped = ?")
                values.append(True)
                values.append(url)
                query = f"UPDATE jobs SET {', '.join(updates)} WHERE url = ?"
                cursor.execute(query, values)
                conn.commit()
                return cursor.rowcount > 0
            return False

    def get_jobs_without_details(self, limit: int = 50) -> List[Dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords, salary, job_type,
                       details_scraped, last_seen_date, stale
                FROM jobs
                WHERE details_scraped = 0 OR details_scraped IS NULL
                ORDER BY discovered_date DESC
                LIMIT ?
            """, (limit,))
            return self._rows_to_jobs(cursor.fetchall())

    def job_exists(self, url: str) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    # ── Cross-site deduplication ──────────────────────────────────────

    def find_similar_job(self, title: str, site_name: str) -> Optional[Dict]:
        """Find a job with the same normalized title from a different site (last 30 days)."""
        normalized = self._normalize_title(title)
        if not normalized or len(normalized) < 10:
            return None

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, site_name, url, title
                FROM jobs
                WHERE site_name != ?
                AND discovered_date > datetime('now', '-30 days')
                ORDER BY discovered_date DESC
                LIMIT 500
            """, (site_name,))

            for row in cursor.fetchall():
                other_normalized = self._normalize_title(row['title'])
                if other_normalized and normalized == other_normalized:
                    return self._row_to_dict(row)
        return None

    @staticmethod
    def _normalize_title(title: str) -> str:
        if not title:
            return ""
        t = title.lower().strip()
        # Replace common separators with spaces before stripping
        t = re.sub(r'[-_/]', ' ', t)
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    # ── Parser config ─────────────────────────────────────────────────

    def save_parser_config(self, site_name: str, url_pattern: str,
                          parser_config: Dict):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO site_parsers
                (site_name, url_pattern, parser_config, last_updated)
                VALUES (?, ?, ?, ?)
            """, (site_name, url_pattern, json.dumps(parser_config),
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_parser_config(self, site_name: str) -> Optional[Dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT parser_config FROM site_parsers WHERE site_name = ?
            """, (site_name,))
            row = cursor.fetchone()
            return json.loads(row['parser_config']) if row else None

    # ── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as cnt FROM jobs")
            total_jobs = cursor.fetchone()['cnt']

            cursor.execute("""
                SELECT COUNT(*) as cnt FROM jobs
                WHERE date(discovered_date) = date('now')
            """)
            today_jobs = cursor.fetchone()['cnt']

            cursor.execute("SELECT COUNT(DISTINCT site_name) as cnt FROM jobs")
            total_sites = cursor.fetchone()['cnt']

            cursor.execute("""
                SELECT COUNT(*) as cnt FROM jobs
                WHERE date(discovered_date) >= date('now', '-7 days')
            """)
            week_jobs = cursor.fetchone()['cnt']

            return {
                'total_jobs': total_jobs,
                'jobs_today': today_jobs,
                'jobs_this_week': week_jobs,
                'total_sites': total_sites
            }

    def cleanup_old_jobs(self, days_to_keep: int = 90) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM jobs
                WHERE date(discovered_date) < date('now', '-' || ? || ' days')
            """, (days_to_keep,))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info("Cleaned up %d jobs older than %d days", deleted_count, days_to_keep)
            return deleted_count

    # ── Staleness Tracking ─────────────────────────────────────────────

    def mark_jobs_seen(self, urls: List[str]):
        """Update last_seen_date for all jobs whose URLs appear in this scrape."""
        if not urls:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            for url in urls:
                cursor.execute(
                    "UPDATE jobs SET last_seen_date = ?, stale = 0 WHERE url = ?",
                    (now, url),
                )
            conn.commit()

    def mark_stale_jobs(self, stale_after_days: int = 30) -> int:
        """Flag jobs not seen in the last *stale_after_days* days as stale."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET stale = 1
                WHERE stale = 0
                  AND last_seen_date IS NOT NULL
                  AND date(last_seen_date) < date('now', '-' || ? || ' days')
            """, (stale_after_days,))
            count = cursor.rowcount
            conn.commit()
            if count:
                logger.info("Marked %d jobs as stale (not seen in %d days)", count, stale_after_days)
            return count

    def get_stale_jobs(self, limit: int = 100) -> List[Dict]:
        """Return jobs flagged as stale."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords, salary, job_type,
                       details_scraped, last_seen_date, stale
                FROM jobs
                WHERE stale = 1
                ORDER BY last_seen_date ASC
                LIMIT ?
            """, (limit,))
            return self._rows_to_jobs(cursor.fetchall())

    # ── Site Health Tracking ──────────────────────────────────────────

    def record_scrape_result(self, site_name: str, success: bool,
                             jobs_found: int = 0, error_message: str = None,
                             http_status: int = None):
        """Record the outcome of scraping a site."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO site_health (site_name, scrape_date, success, jobs_found, error_message, http_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (site_name, datetime.now(timezone.utc).isoformat(),
                  success, jobs_found, error_message, http_status))
            conn.commit()

    def get_failing_sites(self, consecutive_failures: int = 3) -> List[Dict]:
        """Get sites that have failed their last N consecutive scrapes."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT site_name FROM site_health")
            all_sites = [row['site_name'] for row in cursor.fetchall()]

            failing = []
            for site_name in all_sites:
                cursor.execute("""
                    SELECT success, error_message, scrape_date, http_status
                    FROM site_health
                    WHERE site_name = ?
                    ORDER BY scrape_date DESC
                    LIMIT ?
                """, (site_name, consecutive_failures))

                recent = cursor.fetchall()
                if len(recent) >= consecutive_failures and all(not r['success'] for r in recent):
                    failing.append({
                        'site_name': site_name,
                        'consecutive_failures': len(recent),
                        'last_error': recent[0]['error_message'],
                        'last_attempt': recent[0]['scrape_date'],
                        'last_http_status': recent[0]['http_status'],
                    })
            return failing

    def get_site_health_summary(self) -> List[Dict]:
        """Health summary for all sites over the last 7 days."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT site_name,
                       COUNT(*) as total_scrapes,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                       SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
                       SUM(jobs_found) as total_jobs_found,
                       MAX(scrape_date) as last_scrape
                FROM site_health
                WHERE scrape_date > datetime('now', '-7 days')
                GROUP BY site_name
                ORDER BY failures DESC, site_name
            """)
            return self._rows_to_jobs(cursor.fetchall())

    def cleanup_old_health_records(self, days_to_keep: int = 30):
        with self._connect() as conn:
            conn.execute("""
                DELETE FROM site_health
                WHERE date(scrape_date) < date('now', '-' || ? || ' days')
            """, (days_to_keep,))
            conn.commit()

    # ── Data Export ───────────────────────────────────────────────────

    def export_jobs(self, output_file: str, fmt: str = "csv",
                    limit: int = None, site_name: str = None) -> str:
        """Export jobs to CSV or JSON."""
        with self._connect() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, site_name, url, title, description, location,
                       posted_date, discovered_date, keywords, salary, job_type
                FROM jobs
            """
            params = []

            if site_name:
                query += " WHERE site_name = ?"
                params.append(site_name)

            query += " ORDER BY discovered_date DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            jobs = [dict(row) for row in cursor.fetchall()]

        if fmt == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
        else:
            if not jobs:
                logger.warning("No jobs to export")
                return output_file
            fieldnames = list(jobs[0].keys())
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(jobs)

        logger.info("Exported %d jobs to %s", len(jobs), output_file)
        return output_file
