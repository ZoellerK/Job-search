# Job Posting Aggregator

A Python tool that scrapes job postings from multiple websites and generates an RSS feed you can subscribe to. Perfect for monitoring job boards and company career pages that don't offer their own RSS feeds.

## Features

- **Multi-source aggregation**: Monitor multiple job sites from a single feed
- **Auto-detection**: Automatically detects job listings on most career pages
- **Custom parsers**: Configure custom scrapers for sites that need it
- **RSS feed generation**: Creates a standard RSS feed you can use in any feed reader
- **HTML preview**: Generates a browsable HTML page of jobs
- **Duplicate detection**: Tracks jobs you've already seen
- **Keyword filtering**: Filter jobs by keywords per site
- **Daily scheduling**: Optionally run on a schedule

## Installation

1. Clone or download this repository

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. You're ready to go!

## Quick Start

### 1. Add Job Sites

Edit `sites.csv` to add the websites you want to monitor:

```csv
site_name,url,active,keywords
Tech Company,https://example.com/careers,yes,python developer
Startup Co,https://startup.example/jobs,yes,remote
Another Corp,https://corp.example/openings,yes,
```

- **site_name**: A friendly name for the site
- **url**: The URL of the careers/jobs page
- **active**: Set to `yes` to monitor, `no` to disable
- **keywords**: Optional comma-separated keywords to filter jobs

### 2. Run the Aggregator

```bash
python job_aggregator.py
```

This will:
1. Scrape all active sites
2. Find new job postings
3. Generate an RSS feed (`feed.xml`)
4. Create an HTML preview (`preview.html`)
5. Show statistics

### 3. Subscribe to Your Feed

Option A: **Local RSS reader**
- Open `feed.xml` in your RSS reader (Feedly, NetNewsWire, etc.)

Option B: **Web browser**
- Open `preview.html` in your browser to view jobs

Option C: **Serve the feed**
```bash
python -m http.server 8000
```
Then subscribe to `http://localhost:8000/feed.xml`

## Usage

### Basic Commands

```bash
# Run full update (scrape + generate feed)
python job_aggregator.py update

# Just scrape sites
python job_aggregator.py scrape

# Just generate RSS feed from database
python job_aggregator.py feed

# Generate HTML preview
python job_aggregator.py preview

# Show statistics
python job_aggregator.py stats
```

### Setting Up New Sites

The tool includes a setup utility to help configure new job sites:

#### Auto-detect Jobs

```bash
python setup_site.py auto https://example.com/careers
```

This will:
- Attempt to automatically detect job listings
- Show you what it found
- Optionally add the site to your `sites.csv`

#### Test a URL

```bash
python setup_site.py test https://example.com/careers
```

This shows you:
- Page structure
- Common HTML classes
- Common tags
- Number of links

Helpful for understanding how to configure custom parsers.

#### Create Custom Parser

If auto-detection doesn't work well:

```bash
python setup_site.py config https://example.com/careers "Example Company"
```

This launches an interactive wizard that helps you create a custom parser configuration. You'll be asked to identify:
- The HTML element that contains each job
- Where the job title is
- Where the job URL is
- Where location/description are (optional)

The tool saves this configuration and uses it automatically.

### Scheduling

To run the aggregator daily:

```bash
# Run at 9 AM daily (default)
python scheduler.py

# Run at custom time (24-hour format)
python scheduler.py 14:30
```

Or use cron (Linux/Mac):
```bash
# Add to crontab (runs at 9 AM daily)
0 9 * * * cd /path/to/Job-search && python job_aggregator.py update
```

Or Windows Task Scheduler:
- Create a task that runs `python job_aggregator.py update` daily

## Configuration

### config.json

Main configuration file:

```json
{
  "feed": {
    "title": "Job Postings Aggregator",
    "description": "Aggregated job postings from multiple sources",
    "author": "Job Search Tool",
    "link": "http://localhost:8000/feed.xml",
    "language": "en"
  },
  "database": {
    "path": "jobs.db"
  },
  "output": {
    "feed_file": "feed.xml",
    "max_items": 100
  },
  "scraping": {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "timeout": 30,
    "retry_attempts": 3
  }
}
```

### sites.csv

List of sites to monitor:

- **site_name**: Display name for the site
- **url**: Full URL to the jobs/careers page
- **active**: `yes` or `no` to enable/disable
- **keywords**: Optional filter (comma-separated)

Example:
```csv
site_name,url,active,keywords
Python Jobs,https://pythonjobs.github.io/,yes,remote,senior
Remote OK,https://remoteok.com/,yes,python,developer
Y Combinator,https://www.ycombinator.com/jobs,yes,
```

## How It Works

1. **Scraping**: The tool visits each active URL in `sites.csv`
2. **Detection**: Uses either auto-detection or custom parser to find jobs
3. **Filtering**: Applies keyword filters if specified
4. **Storage**: Saves new jobs to SQLite database (`jobs.db`)
5. **Deduplication**: Skips jobs that were already found
6. **Feed Generation**: Creates RSS feed from recent jobs
7. **Preview**: Generates HTML page for easy viewing

## Troubleshooting

### "No jobs detected"

Try these steps:

1. **Test the URL**:
   ```bash
   python setup_site.py test https://example.com/careers
   ```
   Make sure the page loads and shows common elements.

2. **Check the page manually**: Visit the URL in a browser. Are there actually job listings?

3. **Create a custom parser**:
   ```bash
   python setup_site.py config https://example.com/careers "Site Name"
   ```

4. **Inspect the HTML**: Right-click a job listing and "Inspect Element" to see the HTML structure.

### "Connection timeout"

- Check your internet connection
- The site might be blocking automated access
- Try increasing timeout in `config.json`

### "Too many duplicates"

- The tool tracks jobs by URL
- If a site changes job URLs frequently, you may see duplicates
- Consider clearing old jobs from the database periodically

## Project Structure

```
Job-search/
├── job_aggregator.py    # Main orchestrator script
├── scraper.py          # Web scraping logic
├── database.py         # SQLite database management
├── feed_generator.py   # RSS feed generation
├── setup_site.py       # Site configuration tool
├── scheduler.py        # Scheduling script
├── config.json         # Configuration
├── sites.csv           # List of sites to monitor
├── requirements.txt    # Python dependencies
├── jobs.db            # SQLite database (created on first run)
├── feed.xml           # Generated RSS feed
└── preview.html       # Generated HTML preview
```

## Advanced Usage

### Python API

You can import and use the modules in your own scripts:

```python
from job_aggregator import JobAggregator

# Create aggregator
agg = JobAggregator()

# Scrape all sites
new_jobs = agg.scrape_all()

# Get recent jobs from database
jobs = agg.db.get_recent_jobs(limit=50)

# Generate custom feed
agg.generate_feed(max_items=200)
```

### Custom Parsers

Parser configurations are stored in the database. You can also set them programmatically:

```python
from database import JobDatabase

db = JobDatabase()

parser_config = {
    'job_container': {'tag': 'div', 'class': 'job-listing'},
    'title': {'tag': 'h3', 'class': 'job-title'},
    'url': {'tag': 'a', 'attr': 'href'},
    'location': {'tag': 'span', 'class': 'location'}
}

db.save_parser_config('Site Name', 'https://example.com', parser_config)
```

### Email Notifications

To add email notifications, you can use the Python `smtplib`:

```python
# Add to job_aggregator.py
import smtplib
from email.mime.text import MIMEText

def send_email(jobs):
    msg = MIMEText(f"Found {len(jobs)} new jobs!")
    msg['Subject'] = 'New Job Postings'
    msg['From'] = 'you@example.com'
    msg['To'] = 'you@example.com'

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('you@example.com', 'your-password')
        server.send_message(msg)
```

## Tips

1. **Start small**: Add 2-3 sites first, make sure they work
2. **Test before adding**: Use `setup_site.py auto` to test a URL before adding to sites.csv
3. **Use keywords**: Filter noisy sites with targeted keywords
4. **Check regularly**: Run manually a few times before setting up scheduling
5. **Monitor the database**: Use `python job_aggregator.py stats` to see what's being found
6. **Back up your database**: Copy `jobs.db` periodically if you want to keep history

## Limitations

- Sites with heavy JavaScript (React, Vue, etc.) may not work without additional tools like Selenium
- Sites with CAPTCHA or anti-bot measures won't work
- Rate limiting may cause some requests to fail
- Job listings without clear structure may not be detected automatically

## License

This project is provided as-is for personal use. Be respectful of the websites you scrape and follow their terms of service.

## Contributing

Feel free to modify and extend this tool for your needs! Some ideas:

- Add support for Selenium/Playwright for JavaScript-heavy sites
- Integrate with job board APIs (Indeed, LinkedIn, etc.)
- Add email notifications
- Create a web interface
- Add more sophisticated filtering (salary ranges, experience level, etc.)
- Export to different formats (JSON, CSV, etc.)
