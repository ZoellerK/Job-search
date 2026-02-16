# CLAUDE.md — Project Context for AI Assistants

## What This Project Does

Job search aggregator that scrapes 72+ nonprofit/foundation career pages and generates an RSS feed for Feedly. Runs daily via GitHub Actions; the entire workflow can be managed from a phone.

## Architecture

```
job_aggregator.py    — Main orchestrator + CLI (entry point)
scraper.py           — HTTP scraping (requests + optional Playwright)
ats_parsers.py       — Dedicated parsers for Greenhouse, Lever, Workable, Teamtailor, iCIMS, Taleo, Workday, ADP, ApplicantPro
salary_extractor.py  — Regex-based salary extraction from description text
database.py          — SQLite with jobs, site_parsers, site_health tables
feed_generator.py    — RSS 2.0 + HTML preview (Feedly-optimized)
setup_site.py        — Interactive site configuration wizard
config.json          — All runtime settings (feed, scraping, logging)
sites.csv            — Sites to monitor (site_name, url, active, keywords, scrape_details)
```

## Key Conventions

- **Tests before push.** Always run `python -m pytest tests/ -v` and confirm all pass before committing.
- **No secrets in code.** Never commit `.env`, API keys, or credentials.
- **Minimal changes.** Don't refactor surrounding code when fixing a bug. Don't add docstrings/comments to untouched code.
- **SQLite schema changes** use `ALTER TABLE` with `try/except OperationalError` for backward compat (see `database.py:init_database`).

## Adding Sites (The Golden Rule)

**Present → Confirm → Act.** See [ORG_WORKFLOW.md](ORG_WORKFLOW.md) for the full protocol.

1. Check `rejected_sites.txt` and `sites.csv` for duplicates first: `python check_duplicates.py --validate`
2. Present suggestions as a numbered list — make NO file changes
3. Wait for explicit user confirmation
4. Only then append to `sites.csv`

## Common Tasks

```bash
python job_aggregator.py update     # Full cycle: scrape + feed + preview
python job_aggregator.py scrape     # Scrape only
python job_aggregator.py feed       # Regenerate feed from DB
python job_aggregator.py health     # Site health summary
python job_aggregator.py stale      # Show stale job listings
python job_aggregator.py stats      # Database statistics
python job_aggregator.py export json  # Export to JSON
python -m pytest tests/ -v         # Run test suite
```

## Config Quick Reference

All in `config.json`:
- `scraping.max_workers` — parallel thread count (default 5)
- `scraping.timeout` — HTTP timeout in seconds (default 15)
- `logging.level` — INFO, DEBUG, WARNING, etc.
- `feed.relevance_keywords` — custom high/medium keyword lists for scoring
- `feed.include_summary` — include scrape summary in feed (default true)
- `output.max_items` — max jobs in RSS feed (default 100)

## ATS Parsers

When a URL matches a known ATS platform, a dedicated parser runs instead of generic auto-detection. Currently supported: Greenhouse, Lever, Workable, Teamtailor, iCIMS, Taleo, Workday, ADP, ApplicantPro.

To add a new ATS parser:
1. Add detection rule in `detect_ats()` in `ats_parsers.py`
2. Write `parse_<name>(soup, base_url) -> List[Dict]` function
3. Register in `_PARSERS` dict
4. Add tests in `tests/test_ats_parsers.py`

## Test Patterns

- Database tests use `tmp_path` fixture for isolated SQLite files
- Scraper tests mock HTTP with `pytest-mock` / `unittest.mock`
- ATS parser tests use inline HTML strings parsed by BeautifulSoup
- All tests run without network access
