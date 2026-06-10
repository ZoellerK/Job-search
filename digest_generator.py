"""Builds a daily digest of new job postings for push delivery.

The digest is a markdown document listing jobs discovered since the last
run, junk-filtered and sorted by relevance. The GitHub Actions workflow
posts it as a GitHub issue (which triggers a mobile push notification via
the GitHub app), and optionally to an ntfy.sh topic for direct phone push.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

NTFY_SERVER = os.environ.get('NTFY_SERVER', 'https://ntfy.sh')


def _job_line(job: Dict) -> str:
    title = (job.get('title') or 'Unknown Position').strip()
    url = job.get('url') or ''
    parts = [f"**[{title}]({url})**" if url else f"**{title}**"]
    if job.get('site_name'):
        parts.append(job['site_name'])
    extras = []
    if job.get('location'):
        extras.append(job['location'])
    if job.get('salary'):
        extras.append(job['salary'])
    line = f"- {' — '.join(parts)}"
    if extras:
        line += f" ({' · '.join(extras)})"
    return line


def build_digest(jobs: List[Dict], hours: int = 24, filtered_count: int = 0,
                 dashboard_url: str = None,
                 score_fn: Optional[Callable[[Dict], str]] = None) -> str:
    """Build markdown digest from already-filtered jobs.

    score_fn maps a job to a relevance label ('Relevance: High',
    'Relevance: Medium', or ''); jobs are grouped by it when provided.
    """
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lines = [f"## {len(jobs)} new job{'s' if len(jobs) != 1 else ''} "
             f"in the last {hours}h — {today}", ""]

    if score_fn:
        high = [j for j in jobs if score_fn(j) == 'Relevance: High']
        medium = [j for j in jobs if score_fn(j) == 'Relevance: Medium']
        other = [j for j in jobs if j not in high and j not in medium]
    else:
        high, medium, other = [], [], list(jobs)

    for heading, group in [("### ⭐ High relevance", high),
                           ("### Medium relevance", medium),
                           ("### Other new listings", other)]:
        if not group:
            continue
        lines.append(heading)
        # Within a group, keep newest first (input order) but cluster by org
        by_site: Dict[str, List[Dict]] = {}
        for job in group:
            by_site.setdefault(job.get('site_name') or 'Unknown', []).append(job)
        for site in by_site:
            for job in by_site[site]:
                lines.append(_job_line(job))
        lines.append("")

    footer = []
    if filtered_count:
        footer.append(f"{filtered_count} obvious non-job link"
                      f"{'s' if filtered_count != 1 else ''} filtered out.")
    if dashboard_url:
        footer.append(f"[Full dashboard]({dashboard_url})")
    if footer:
        lines.append("---")
        lines.append(' · '.join(footer))

    return '\n'.join(lines).rstrip() + '\n'


def send_ntfy(topic: str, title: str, message: str,
              click_url: str = None, server: str = None) -> bool:
    """Push a notification to an ntfy.sh topic. Returns True on success."""
    server = server or NTFY_SERVER
    headers = {'Title': title, 'Tags': 'briefcase'}
    if click_url:
        headers['Click'] = click_url
    try:
        resp = requests.post(
            f"{server.rstrip('/')}/{topic}",
            data=message.encode('utf-8'),
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("ntfy push sent to topic %s", topic)
        return True
    except requests.RequestException as e:
        logger.error("ntfy push failed: %s", e)
        return False


def build_ntfy_message(jobs: List[Dict], max_listed: int = 6) -> str:
    """Short plain-text summary for the notification body."""
    lines = []
    for job in jobs[:max_listed]:
        site = f" ({job['site_name']})" if job.get('site_name') else ''
        lines.append(f"• {job.get('title', 'Unknown')}{site}")
    remaining = len(jobs) - max_listed
    if remaining > 0:
        lines.append(f"…and {remaining} more")
    return '\n'.join(lines)
