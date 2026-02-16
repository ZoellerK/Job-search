# Job Posting RSS Feed

A Python tool that scrapes job postings from multiple websites and generates an RSS feed you can subscribe to. Monitors job boards and company career pages that don't offer their own RSS feeds.

## Features

- **Multi-source aggregation** — monitor 72+ career pages from a single feed
- **ATS-specific parsers** — dedicated parsers for Greenhouse, Lever, Workable, Teamtailor, iCIMS, Taleo, Workday, ADP, and ApplicantPro (12 sites covered)
- **Auto-detection** — automatically finds job listings on career pages without a dedicated parser
- **Salary extraction** — regex-based extraction of compensation from job description text (`$60k-$80k`, `$120,000/year`, etc.)
- **Relevance scoring** — jobs scored against configurable keywords and tagged High/Medium for Feedly filtering
- **Stale job detection** — tracks when listings were last seen; hides jobs not seen in 30+ days from the feed
- **RSS feed generation** — standard RSS 2.0 feed optimised for Feedly with rich HTML content
- **HTML preview** — browsable HTML page of recent jobs
- **Duplicate detection** — tracks jobs by URL; cross-site dedup via fuzzy title matching
- **Keyword filtering** — filter jobs per site with comma-separated keywords
- **Site health tracking** — flags sites that fail 3+ consecutive scrapes (alerts appear in your feed)
- **Smart rate limiting** — per-domain throttling with automatic back-off on 429s
- **JS rendering** — optional Playwright fallback for JavaScript-heavy career pages
- **Data export** — export jobs to CSV or JSON
- **Structured logging** — configurable log level; logs to console + `job_aggregator.log`
- **Config validation** — safe defaults for missing config keys; CSV validation catches empty URLs and duplicates
- **Automated tests** — 128-test pytest suite with unit, integration, and mocked HTTP tests
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
1. Scrape all active sites (5 in parallel, configurable)
2. Use ATS-specific parsers for known platforms, auto-detect for the rest
3. Extract salary from descriptions when no explicit salary field exists
4. Deduplicate against existing jobs (URL + cross-site fuzzy title matching)
5. Record site health for each scrape
6. Flag stale jobs not seen in 30+ days
7. Generate `feed.xml` (RSS) and `preview.html` with relevance scoring

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
python job_aggregator.py stale     # Show stale job listings (not seen in 30+ days)
python job_aggregator.py export csv              # Export all jobs to jobs_export.csv
python job_aggregator.py export json             # Export all jobs to jobs_export.json
python job_aggregator.py export json my_jobs.json  # Export to custom file
```

## Site Setup Tools

```bash
python setup_site.py auto https://example.com/careers    # Auto-detect jobs (uses ATS parser if detected)
python setup_site.py test https://example.com/careers    # Analyse page structure
python setup_site.py config https://example.com/careers "Company Name"  # Create custom parser
```

The `auto` command automatically detects ATS platforms (Greenhouse, Lever, etc.) and uses the dedicated parser for better results before falling back to generic detection.

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
    "retry_attempts": 2,
    "max_workers": 5
  },
  "logging": { "level": "INFO" },
  "cleanup": { "days_to_keep": 90, "stale_after_days": 30 }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `feed.include_site_in_title` | `true` | Append site name to each job title |
| `feed.simple_descriptions` | `false` | Use plain text instead of rich HTML |
| `feed.include_summary` | `true` | Add scrape summary + health alerts as first feed item |
| `feed.relevance_keywords` | *(built-in)* | Custom `{"high": [...], "medium": [...]}` keyword lists for scoring |
| `scraping.max_workers` | `5` | Number of parallel scraping threads |
| `scraping.timeout` | `15` | HTTP request timeout in seconds |
| `logging.level` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `cleanup.days_to_keep` | `90` | Delete jobs older than this many days |
| `cleanup.stale_after_days` | `30` | Mark jobs as stale after this many days unseen |

Missing config keys are filled with safe defaults automatically, so a minimal `config.json` (e.g. just `{"database": {"path": "jobs.db"}}`) will work.

## ATS Parsers

Sites hosted on common Applicant Tracking Systems get dedicated parsers that extract richer metadata than generic auto-detection:

| ATS | Example Sites | Data Extracted |
|-----|--------------|----------------|
| Greenhouse | Omidyar Network, FSG | title, URL, location, department |
| Lever | RepresentUs, DRK Foundation | title, URL, location, job type, department |
| Workable | Echoing Green | title, URL, location, job type |
| Teamtailor | Founders Pledge | title, URL, location, job type |
| iCIMS | Brookings Institution | title, URL, location, job type |
| Taleo | Freedom House | title, URL, location |
| Workday | Gates Foundation | title, URL, location, posted date |
| ADP | Rockefeller Foundation | title, URL, location |
| ApplicantPro | Carnegie Endowment | title, URL, location, department |

ATS type is detected automatically from the URL. Falls back to generic scraping if the ATS parser finds nothing.

## Site Health Tracking

Every scrape records success/failure per site in a `site_health` table. When a site fails 3+ times in a row:

- A **warning banner** appears in the RSS feed summary item (visible in Feedly)
- The `health` command shows a full breakdown
- The log file records the errors

This lets you know immediately when a site changes its URL or blocks scraping, without auto-disabling anything.

## How It Works

1. **Scraping** — visits each active URL in `sites.csv` (configurable parallel threads)
2. **ATS detection** — checks if URL matches a known ATS platform; uses dedicated parser if so
3. **Auto-detection** — falls back to heuristic-based job listing detection for non-ATS sites
4. **JS fallback** — if the page looks like a JS-rendered shell and Playwright is installed, retries with headless Chromium
5. **Salary extraction** — scans description text for compensation patterns when no salary field exists
6. **Filtering** — applies keyword filters if configured
7. **Deduplication** — skips jobs with duplicate URLs; also checks for matching normalised titles across sites
8. **Staleness tracking** — marks all scraped URLs as "seen"; flags jobs missing for 30+ days
9. **Health tracking** — records success/failure + error details per site
10. **Storage** — saves new jobs to SQLite (`jobs.db`)
11. **Feed generation** — creates RSS 2.0 feed with rich HTML content, relevance scoring, metadata categories, and health alerts

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

128 tests covering database operations, scraper logic (with mocked HTTP), feed generation, ATS parsers, salary extraction, relevance scoring, site health, staleness tracking, cross-site dedup, data export, end-to-end integration, CSV validation, and config defaults.

## Project Structure

```
Job-search/
├── job_aggregator.py    # Main orchestrator + CLI
├── scraper.py           # Web scraping (requests + optional Playwright)
├── ats_parsers.py       # ATS-specific parsers (Greenhouse, Lever, Workday, etc.)
├── salary_extractor.py  # Salary extraction from description text
├── database.py          # SQLite: jobs, site_parsers, site_health tables
├── feed_generator.py    # RSS 2.0 + HTML preview generation
├── setup_site.py        # Interactive site configuration tool
├── scheduler.py         # Daily scheduling wrapper
├── config.json          # Configuration
├── sites.csv            # Sites to monitor (72+ active)
├── CLAUDE.md            # Project context for AI assistants
├── requirements.txt     # Python dependencies
├── pytest.ini           # Test configuration
├── tests/               # Automated test suite (128 tests)
│   ├── test_database.py
│   ├── test_scraper.py
│   ├── test_feed_generator.py
│   ├── test_ats_parsers.py
│   ├── test_salary_extractor.py
│   └── test_integration.py
├── jobs.db              # SQLite database (created on first run)
├── feed.xml             # Generated RSS feed
├── preview.html         # Generated HTML preview
└── job_aggregator.log   # Log file
```

## Limitations

- Sites with CAPTCHA or aggressive anti-bot measures won't work
- Workday, Taleo, and ADP pages are heavily JS-rendered — parsers work best with Playwright installed
- Cross-site dedup uses exact normalised title matching — very similar but non-identical titles won't match

## License

This project is provided as-is for personal use. Be respectful of the websites you scrape and follow their terms of service.
