# Job Detail Scraping Enhancement Guide

## Overview

The job scraping system has been enhanced to extract **full job descriptions** and additional metadata from individual job posting pages. This solves the problem where many job boards (like PAC.org) only show job titles and links on their listing pages, without descriptions.

## What's New

### 1. Enhanced Data Extraction

The system can now extract from individual job pages:

- **Full job descriptions** (up to 5,000 characters)
- **Location** information
- **Salary/compensation** details
- **Job type** (full-time, part-time, contract, etc.)
- **Posted date**

### 2. Database Enhancements

The database schema now includes:

- `salary` - Salary or compensation information
- `job_type` - Employment type (full-time, part-time, etc.)
- `details_scraped` - Boolean flag indicating if detail page was scraped

### 3. Site Configuration

The `sites.csv` file now supports a `scrape_details` column:

```csv
site_name,url,active,keywords,scrape_details
PAC.org,https://pac.org/jobs,yes,,yes
OnPurpose Careers,https://www.onpurposecareers.org/jobboard,yes,,no
```

- `yes` - Scrape individual job detail pages (recommended for sites with minimal listing info)
- `no` - Only scrape listing page (default, faster)

### 4. Enhanced RSS Feed

The RSS feed now displays:

- Full job descriptions in rich HTML format
- Job type and salary in metadata header
- Better categorization for RSS readers like Feedly

## How It Works

### Automatic Detail Page Scraping

When `scrape_details` is set to `yes` for a site:

1. **Listing page** is scraped to find job URLs and titles
2. **Individual job pages** are visited (up to 20 jobs per site to be respectful)
3. **Common patterns** are used to extract:
   - Job descriptions from `<div class="description">`, `<section class="job-details">`, etc.
   - Location from elements with "location", "city", "region" classes
   - Salary from elements with "salary", "compensation" classes
   - Job type from elements with "job-type", "employment-type" classes
   - Posted date from `<time>` elements or date-related classes

4. **Extracted data** is merged with listing page data
5. **Database** is updated with enriched information

### Intelligent Pattern Detection

The scraper uses multiple fallback strategies to find job descriptions:

```python
# Strategy 1: Common description classes/IDs
<div class="job-description">...</div>
<section id="description">...</section>

# Strategy 2: Main content area
<main>...largest text block...</main>

# Strategy 3: Paragraph aggregation
Multiple <p> tags combined into description
```

## Configuration Guide

### Enabling Detail Scraping for a Site

Edit `sites.csv`:

```csv
site_name,url,active,keywords,scrape_details
PAC.org,https://pac.org/jobs,yes,,yes
```

The last column (`scrape_details`) controls whether individual job pages are scraped.

### When to Enable Detail Scraping

**Enable (`yes`) when:**
- Listing page shows only titles and links
- You need full job descriptions for RSS readers
- Site has consistent job detail page structure

**Disable (`no`) when:**
- Listing page already includes descriptions
- Site blocks automated requests
- You want faster scraping (less respectful of server load)

### Scraping Rate Limits

To be respectful of servers:
- Maximum 20 jobs enriched per site per run
- 0.5 second delay between detail page requests
- Automatic retry with exponential backoff on failures

## Usage Examples

### Running a Full Update with Detail Scraping

```bash
# Run full update (includes detail scraping for enabled sites)
python job_aggregator.py update

# Or just scrape without feed generation
python job_aggregator.py scrape
```

### Testing Detail Scraping

```bash
# Test scraping individual job detail pages
python test_detail_scraping.py details

# Test enriching a list of jobs
python test_detail_scraping.py enrich

# Show database statistics
python test_detail_scraping.py stats

# Run all tests
python test_detail_scraping.py
```

### Programmatic Usage

```python
from scraper import JobScraper

scraper = JobScraper()

# Scrape a single job detail page
details = scraper.scrape_job_details('https://pac.org/job/some-job-id')
print(details['description'])  # Full job description
print(details['location'])     # Job location
print(details['salary'])       # Salary info

# Enrich a list of jobs with details
jobs = [
    {'title': 'Manager', 'url': 'https://...', 'description': None},
    {'title': 'Director', 'url': 'https://...', 'description': None}
]

enriched = scraper.enrich_jobs_with_details(jobs, max_jobs=10)
```

## Database Management

### Updating Existing Jobs with Details

To scrape details for jobs already in the database:

```python
from database import JobDatabase
from scraper import JobScraper

db = JobDatabase()
scraper = JobScraper()

# Get jobs without details
jobs_without_details = db.get_jobs_without_details(limit=20)

# Enrich them
for job in jobs_without_details:
    details = scraper.scrape_job_details(job['url'])

    if details:
        db.update_job_details(
            url=job['url'],
            description=details.get('description'),
            location=details.get('location'),
            salary=details.get('salary'),
            job_type=details.get('job_type'),
            posted_date=details.get('posted_date')
        )
```

## RSS Feed Improvements

### Enhanced Job Entries

RSS feed items now include:

```xml
<item>
  <title>Manager, Corporate Communications - PAC.org</title>
  <description>
    📍 Washington, DC • 💼 Full-time • 💰 $80,000-$100,000 • 🏢 PAC.org

    [Full job description preview...]
  </description>
  <content:encoded>
    <div style='background: #667eea; color: white; ...'>
      📍 <strong>Washington, DC</strong> | 🏢 PAC.org | 💼 Full-time | 💰 $80,000-$100,000
    </div>
    <div>
      <p>[Full formatted job description with headings and structure...]</p>
    </div>
    <div style='margin-top: 24px; ...'>
      <a href="https://pac.org/job/..." style='background: #667eea; ...'>
        Apply for this Position
      </a>
    </div>
  </content:encoded>
  <category>PAC.org</category>
  <category>Full-time</category>
  <category>Leadership</category>
</item>
```

### Better Categorization

Jobs are automatically categorized by:

- **Work arrangement**: Remote, Hybrid, On-site
- **Employment type**: Full-time, Part-time, Contract, Internship
- **Seniority**: Senior, Junior, Leadership
- **Site name**: For filtering by source

## Troubleshooting

### Site Blocks Requests

**Problem**: Some sites (like PAC.org) may return 403 errors

**Solutions**:
1. The scraper uses a realistic User-Agent string
2. Respects rate limits (0.5s between requests)
3. If site consistently blocks, set `scrape_details=no`

### No Descriptions Extracted

**Problem**: Detail pages scraped but no descriptions found

**Solutions**:
1. Check if site uses JavaScript to load content (scraper only handles static HTML)
2. Create custom parser config using `setup_site.py`
3. Inspect page structure and update scraper patterns in `scraper.py`

### Database Migration

If you get SQL errors about missing columns:

```bash
# The database automatically adds new columns when you run the aggregator
python job_aggregator.py stats

# Or manually update:
python -c "from database import JobDatabase; JobDatabase().init_database()"
```

## Performance Considerations

### Scraping Time

- **Without detail scraping**: ~1-5 seconds per site
- **With detail scraping**: ~15-30 seconds per site (20 jobs × 0.5s + page load)

### Storage

- Job descriptions add ~1-3 KB per job
- Database size will increase moderately
- Old jobs auto-deleted after 90 days

### Respectful Scraping

The system is designed to be respectful:
- Rate limits prevent server overload
- Maximum 20 jobs per site prevents abuse
- User-Agent identifies as a bot
- Exponential backoff on failures

## Future Enhancements

Potential improvements:

1. **JavaScript rendering** - Support sites that load content with JavaScript
2. **AI-powered extraction** - Use LLMs to extract structured data from any page
3. **Incremental updates** - Only scrape new jobs, not already-scraped ones
4. **Custom selectors per site** - Store detail page selectors in database
5. **Parallel detail scraping** - Scrape multiple detail pages simultaneously

## Questions?

For issues or questions:
- Review the test script: `test_detail_scraping.py`
- Check scraper code: `scraper.py` (lines 409-500)
- Examine database schema: `database.py`
- View feed generation: `feed_generator.py`
