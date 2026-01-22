# Job Aggregator Improvements

This document describes the recent improvements to the RSS feed presentation and URL validation.

## RSS Feed Improvements

### New Features

1. **Configurable Title Format**
   - Control whether site names appear in RSS item titles
   - Set `include_site_in_title: false` in config.json to show only job titles
   - Site information is still available in the description and as a separate source element

2. **Simple Description Mode**
   - Option for plain-text descriptions for RSS readers that don't handle HTML well
   - Set `simple_descriptions: true` in config.json
   - Provides cleaner, more readable plain-text format

3. **Enhanced HTML Descriptions**
   - Improved styling with better visual hierarchy
   - Cleaner metadata presentation
   - Better paragraph formatting
   - Styled keyword tags
   - Prominent "Apply Now" button

4. **Better RSS Metadata**
   - Added `<source>` element for better RSS reader support
   - Added `<author>` element with site name
   - Site names added as categories for filtering
   - More robust date handling (omits pubDate if not available)

5. **Condensed Summary**
   - More compact scraping summary at top of feed
   - Collapsible site breakdown using `<details>` HTML element
   - Only shows sites with new jobs
   - Can be disabled with `include_summary: false` in config.json

### Configuration Options

Add these to your `config.json` under the `feed` section:

```json
{
  "feed": {
    "title": "Job Postings Aggregator",
    "description": "Aggregated job postings from multiple sources",
    "author": "Job Search Tool",
    "link": "http://localhost:8000/feed.xml",
    "language": "en",
    "include_site_in_title": true,     // Show site name in titles
    "simple_descriptions": false,       // Use plain-text descriptions
    "include_summary": true             // Include scraping summary
  }
}
```

### Example Configurations

**Minimal Feed (Clean titles, no summary):**
```json
"include_site_in_title": false,
"simple_descriptions": true,
"include_summary": false
```

**Rich Feed (Default - full HTML, with summary):**
```json
"include_site_in_title": true,
"simple_descriptions": false,
"include_summary": true
```

## URL Validation Tool

### New Script: `validate_sites.py`

A comprehensive tool to validate all career site URLs and find better alternatives.

### Features

1. **URL Validation**
   - Checks HTTP status codes
   - Detects redirects
   - Identifies 404 errors
   - Handles timeouts and connection errors

2. **ATS Detection**
   - Automatically identifies applicant tracking systems (ATS)
   - Supports: Greenhouse, Lever, Workable, Workday, iCIMS, Taleo, and more
   - Suggests better ATS URLs when found

3. **Comprehensive Reporting**
   - Categorizes results (OK, Redirects, Errors, Better URLs)
   - Generates detailed text report
   - Prioritizes issues needing attention

### Usage

```bash
# Validate all sites in sites.csv
python validate_sites.py

# Validate a specific file
python validate_sites.py my_sites.csv
```

### Output

The script generates:
1. **Console output** - Real-time validation progress with status emojis
2. **validation_report.txt** - Detailed report with sections:
   - Summary statistics
   - Errors and 404s (needs attention)
   - Better ATS URLs found
   - Redirects (may need updating)
   - Valid URLs (no action needed)

### Report Example

```
================================================================================
SITE VALIDATION REPORT
================================================================================

SUMMARY
--------------------------------------------------------------------------------
Total sites checked: 56
✅ Valid URLs: 48
🔄 Redirects: 5
❌ Errors/404s: 2
💡 Better URLs found: 1

================================================================================
ERRORS AND 404s (NEEDS ATTENTION)
================================================================================

Hill-Snowdon Foundation
  Current URL: https://www.hillsnowdon.org/careers/
  Status: 404 - Page not found
  Action: NEEDS NEW URL

================================================================================
BETTER ATS URLS FOUND
================================================================================

Echoing Green
  Current URL: https://echoinggreen.org/careers/
  Suggested URL: https://apply.workable.com/echoing-green/
  Action: CONSIDER UPDATING
```

### Recommended Workflow

1. **Run validation regularly** (monthly or when adding new sites)
   ```bash
   python validate_sites.py
   ```

2. **Review the report**
   - Fix errors/404s immediately
   - Consider updating to better ATS URLs
   - Update redirect URLs to final destinations

3. **Update sites.csv** with improved URLs

4. **Re-run to verify** changes

### Integration with GitHub Actions

Add to your workflow to automatically validate URLs:

```yaml
- name: Validate Career Site URLs
  run: python validate_sites.py
  continue-on-error: true  # Don't fail workflow on validation errors
```

## Benefits

### RSS Feed Improvements
- **Better readability** - Cleaner formatting, easier to scan
- **More flexible** - Configure to match your RSS reader's capabilities
- **Better organization** - Use categories and source elements for filtering
- **Less clutter** - Optional summary, condensed when shown

### URL Validation
- **Catch broken links** - Find 404s before users do
- **Stay current** - Detect when sites move or change URLs
- **Find better sources** - Discover direct ATS links for more reliable scraping
- **Save time** - Automated checking vs. manual verification

## Migration Notes

### Existing Users

The improvements are **backward compatible**. Your existing setup will continue to work with the enhanced defaults:
- Site names in titles (as before)
- Rich HTML descriptions (improved)
- Summary included (more condensed now)

To customize, add the new configuration options to your `config.json`.

### RSS Reader Compatibility

Most modern RSS readers handle HTML well. If yours doesn't, try:
```json
"simple_descriptions": true
```

This provides plain-text descriptions that work everywhere.

## Future Enhancements

Potential additions:
- Slack/Discord webhook integration
- Advanced filtering (salary, remote, etc.)
- Job deduplication across sites
- Custom ATS parsers
- Image/logo support in feed
