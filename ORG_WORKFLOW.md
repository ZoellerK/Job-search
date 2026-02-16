# Organization Discovery & Approval Workflow

## Overview

```
Discovery → candidates.csv → Review (checkboxes) → sites.csv / rejected_sites.txt
```

All file writes go through `manage_sites.py`. Never edit `sites.csv` or `rejected_sites.txt` by hand.

---

## Phase 1: Discovery

When the user asks for new organizations:

1. **Run patterns first** to understand what's been approved:
   ```bash
   python manage_sites.py patterns
   ```

2. **Find candidates** and add them to the staging area:
   ```bash
   python manage_sites.py add "Org Name" "https://example.org/careers" --category "Democracy" --test
   ```
   The `--test` flag fetches the URL, detects ATS, and counts jobs.
   Duplicates are automatically blocked (checks names AND URLs against sites.csv, rejected_sites.txt, and candidates.csv).

3. **For bulk discovery**, create a text file and batch-add:
   ```bash
   # candidates_new.txt — one per line: Name - URL
   python manage_sites.py add-batch candidates_new.txt --category "Foundations"
   ```

4. **Check staging status**:
   ```bash
   python manage_sites.py status
   ```

**No manual CSV editing happens in this phase.**

---

## Phase 2: Review (Checkboxes)

Generate a review file for the user:

```bash
python manage_sites.py review
# or limit batch size:
python manage_sites.py review --batch 20
```

This creates a markdown file like `review_2026-02-16.md`:

```markdown
# Candidate Review (2026-02-16)

15 candidates to review. Check `[x]` to approve, leave `[ ]` to reject.

## Democracy & Governance (5)

- [ ] **1. Org Name** — https://example.org/careers
  Greenhouse | 12 jobs

- [ ] **2. Another Org** — https://another.org/jobs
  Lever | 5 jobs

## Foundations (10)

- [ ] **3. Big Foundation** — https://big.org/careers
  Workday | 8 jobs
...
```

**Present this file to the user.** They check `[x]` the ones they want.

---

## Phase 3: Process

After the user marks their choices:

```bash
python manage_sites.py process review_2026-02-16.md
```

This:
- Moves `[x]` checked items → appends to `sites.csv`
- Moves `[ ]` unchecked items → appends to `rejected_sites.txt`
- Updates candidate status in `candidates.csv`

**Alternative: quick approve/reject by ID without a review file:**
```bash
python manage_sites.py approve 1 3 5 7
python manage_sites.py reject 2 4 6
```

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `manage_sites.py add <name> <url>` | Stage a candidate |
| `manage_sites.py add-batch <file>` | Stage many candidates |
| `manage_sites.py test <url>` | Test URL without staging |
| `manage_sites.py status` | Show pending/approved/rejected counts |
| `manage_sites.py review` | Generate checkbox review file |
| `manage_sites.py process <file>` | Apply review decisions |
| `manage_sites.py approve <ids>` | Quick approve by ID |
| `manage_sites.py reject <ids>` | Quick reject by ID |
| `manage_sites.py patterns` | Analyze what gets approved |
| `manage_sites.py clear` | Remove processed candidates from staging |

---

## Dedup Rules

Candidates are checked against three sources:
1. **sites.csv** — name match (normalized) AND URL/domain match
2. **rejected_sites.txt** — name match (normalized) AND URL/domain match
3. **candidates.csv** — name match AND URL match (prevents re-adding)

Name normalization: lowercase, strip "the" prefix, strip common suffixes (Foundation, Fund, Institute, etc.).

---

## Approval Patterns

Run `python manage_sites.py patterns` to see:
- ATS platform distribution across approved sites
- URL pattern breakdown (org-hosted vs. ATS-hosted)
- Common name terms
- Approval rate vs rejection rate

Use these patterns to prioritize discovery toward categories and org types the user tends to approve.
