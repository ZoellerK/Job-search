# Idealist Scraper Fix

## Problem
The Idealist scraper was returning **0 jobs** while other scrapers were working (e.g., PAC.org had 513 jobs).

## Root Cause
1. **Wrong URL**: `sites.csv` had `/en/jobs` but jobs are at `/en/nonprofit-jobs`
2. **Parser config** is looking for links containing `/en/nonprofit-job/` (singular)
3. **Possible issue**: Idealist might use JavaScript rendering (needs verification)

## Changes Made

### 1. Updated sites.csv
```csv
# OLD:
Idealist,https://www.idealist.org/en/jobs,yes,

# NEW:
Idealist,https://www.idealist.org/en/nonprofit-jobs,yes,
```

### 2. Created Diagnostic Script
Run `diagnose_idealist.py` **on your local machine** (not in Claude Code environment) to:
- Verify the correct URL pattern for job links
- Check if JavaScript rendering is needed
- See examples of actual job links

```bash
python3 diagnose_idealist.py
```

## Next Steps

### If this fixes it:
Great! The scraper should start finding Idealist jobs on the next run.

### If still no jobs after next scrape:
The diagnostic script will show you:

1. **If the URL pattern is wrong**: Update the parser config in the database
   ```python
   from database import JobDatabase
   db = JobDatabase()
   db.save_parser_config("Idealist", {
       'url_pattern': '/correct/pattern/here/',  # Based on diagnostic output
       'exclude_patterns': ['/apply', '/share', '/edit']
   })
   ```

2. **If JavaScript rendering is needed**: We'll need to add Selenium/Playwright support
   to the scraper for sites that load jobs dynamically

3. **If the page structure changed completely**: We might need to switch from
   URL pattern matching to CSS selector-based scraping

## Testing

Run the test script locally to verify:
```bash
python3 test_idealist.py
```

This will attempt to scrape Idealist and show you what it finds.

## Parser Config Reference

Current Idealist parser config in database:
```python
{
    'url_pattern': '/en/nonprofit-job/',  # Links must contain this
    'exclude_patterns': ['/apply', '/share', '/edit']  # Exclude these
}
```

This tells the scraper: "Find all links that contain `/en/nonprofit-job/` but exclude
ones with `/apply`, `/share`, or `/edit` in the URL."
