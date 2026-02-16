# Job Posting RSS Feed

A Python tool that scrapes job postings from multiple websites and generates an RSS feed you can subscribe to. Monitors job boards and company career pages that don't offer their own RSS feeds.

## Features

- **Multi-source aggregation** — monitor 70+ career pages from a single feed
- **Auto-detection** — automatically finds job listings on most career pages
- **Custom parsers** — configure site-specific scrapers when auto-detect isn't enough
- **RSS feed generation** — standard RSS 2.0 feed optimised for Feedly
- **HTML preview** — browsable HTML page of recent jobs
- **Duplicate detection** — tracks jobs by URL; cross-site dedup via fuzzy title matching
- **Keyword filtering** — filter jobs per site with comma-separated keywords
- **Site health tracking** — automatically flags sites that fail 3+ consecutive scrapes (alerts appear in your feed)
- **Smart rate limiting** — per-domain throttling with automatic back-off on 429s
- **JS rendering** — optional Playwright fallback for JavaScript-heavy career pages
- **Data export** — export jobs to CSV or JSON
- **Structured logging** — logs to console + `job_aggregator.log` for debugging
- **Automated tests** — 44-test pytest suite with mocked HTTP
- **GitHub Actions** — runs automatically in the cloud (no computer needed)

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

**Optional** — for JavaScript-heavy sites (React/Vue career pages):

```bash
pip install playwright && playwright install chromium
```

### 2. Add job sites

Edit `sites.csv`:

```csv
site_name,url,active,keywords,scrape_details
Democracy Fund,https://democracyfund.org/about/jobs/,yes,,no
CSIS,https://careers.csis.org/,yes,,no
```

| Column | Description |
|--------|-------------|
| `site_name` | Display name for the site |
| `url` | URL of the careers/jobs page |
| `active` | `yes` to monitor, `no` to disable |
| `keywords` | Optional comma-separated filter keywords |
| `scrape_details` | `yes` to also scrape individual job detail pages |

### 3. Run

```bash
python job_aggregator.py          # Full update (scrape + feed + preview)
```

This will:
1. Scrape all active sites (5 in parallel)
2. Deduplicate against existing jobs (URL + cross-site fuzzy title matching)
3. Record site health for each scrape
4. Generate `feed.xml` (RSS) and `preview.html`
5. Flag any sites failing 3+ times in a row (alert appears in feed)

### 4. Subscribe

- **Feedly / RSS reader** — subscribe to the published URL or local `feed.xml`
- **Browser** — open `preview.html`
- **Local server** — `python -m http.server 8000` then subscribe to `http://localhost:8000/feed.xml`

## Commands

```bash
python job_aggregator.py update    # Full update cycle (default)
python job_aggregator.py scrape    # Scrape only (no feed generation)
python job_aggregator.py feed      # Regenerate feed from database
python job_aggregator.py preview   # Regenerate HTML preview
python job_aggregator.py stats     # Show database statistics
python job_aggregator.py health    # Show site health summary + alerts
python job_aggregator.py export csv              # Export all jobs to jobs_export.csv
python job_aggregator.py export json             # Export all jobs to jobs_export.json
python job_aggregator.py export json my_jobs.json  # Export to custom file
```

## Site Setup Tools

```bash
python setup_site.py auto https://example.com/careers    # Auto-detect jobs
python setup_site.py test https://example.com/careers    # Analyse page structure
python setup_site.py config https://example.com/careers "Company Name"  # Create custom parser
```

## Configuration

### config.json

```json
{
  "feed": {
    "title": "Job Postings RSS Feed",
    "description": "Aggregated job postings",
    "author": "Job Search Tool",
    "link": "https://yourdomain.github.io/Job-search/feed.xml",
    "include_site_in_title": true,
    "simple_descriptions": false,
    "include_summary": true
  },
  "database": { "path": "jobs.db" },
  "output": { "feed_file": "feed.xml", "max_items": 100 },
  "scraping": {
    "user_agent": "Mozilla/5.0 ...",
    "timeout": 15,
    "retry_attempts": 2
  }
}
```

| Feed option | Default | Description |
|-------------|---------|-------------|
| `include_site_in_title` | `true` | Append site name to each job title |
| `simple_descriptions` | `false` | Use plain text instead of rich HTML |
| `include_summary` | `true` | Add scrape summary + health alerts as first feed item |

## Site Health Tracking

Every scrape records success/failure per site in a `site_health` table. When a site fails 3+ times in a row:

- A **warning banner** appears in the RSS feed summary item (visible in Feedly)
- The `health` command shows a full breakdown
- The log file records the errors

This lets you know immediately when a site changes its URL or blocks scraping, without auto-disabling anything.

## How It Works

1. **Scraping** — visits each active URL in `sites.csv` (5 threads)
2. **Detection** — uses custom parser config (if saved) or auto-detection heuristics
3. **JS fallback** — if the page looks like a JS-rendered shell and Playwright is installed, retries with headless Chromium
4. **Rate limiting** — per-domain throttling; automatic exponential back-off on HTTP 429
5. **Filtering** — applies keyword filters if configured
6. **Deduplication** — skips jobs with duplicate URLs; also checks for matching normalised titles across sites
7. **Health tracking** — records success/failure + error details per site
8. **Storage** — saves new jobs to SQLite (`jobs.db`)
9. **Feed generation** — creates RSS 2.0 feed with rich HTML content, metadata categories, and health alerts

## Scheduling

### With the built-in scheduler

```bash
python scheduler.py          # Runs at 9 AM daily (default)
python scheduler.py 14:30    # Custom time
```

### With cron (Linux/Mac)

```bash
0 9 * * * cd /path/to/Job-search && python job_aggregator.py update
```

### With GitHub Actions

See the `.github/workflows/` directory — runs automatically in the cloud. Edit `sites.csv` from the GitHub web UI or mobile app.

**[See PHONE_SETUP.md for managing everything from your phone](PHONE_SETUP.md)**

## Running Tests

```bash
python -m pytest tests/ -v
```

44 tests covering database operations, scraper logic (with mocked HTTP), feed generation, site health, cross-site dedup, and data export.

## Project Structure

```
Job-search/
├── job_aggregator.py    # Main orchestrator + CLI
├── scraper.py           # Web scraping (requests + optional Playwright)
├── database.py          # SQLite: jobs, site_parsers, site_health tables
├── feed_generator.py    # RSS 2.0 + HTML preview generation
├── setup_site.py        # Interactive site configuration tool
├── scheduler.py         # Daily scheduling wrapper
├── config.json          # Configuration
├── sites.csv            # Sites to monitor
├── requirements.txt     # Python dependencies
├── pytest.ini           # Test configuration
├── tests/               # Automated test suite
│   ├── test_database.py
│   ├── test_scraper.py
│   └── test_feed_generator.py
├── jobs.db              # SQLite database (created on first run)
├── feed.xml             # Generated RSS feed
├── preview.html         # Generated HTML preview
└── job_aggregator.log   # Log file
```

## Limitations

- Sites with CAPTCHA or aggressive anti-bot measures won't work
- Some ATS platforms (Workday, Taleo) may need custom parser configs
- Cross-site dedup uses exact normalised title matching — very similar but non-identical titles won't match

## License

This project is provided as-is for personal use. Be respectful of the websites you scrape and follow their terms of service.
