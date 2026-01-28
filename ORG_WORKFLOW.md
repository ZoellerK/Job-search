# Organization Suggestion & Addition Workflow

## The Golden Rule

**Present → Confirm → Act.** Never modify `sites.csv` or `rejected_sites.txt` without explicit user confirmation with echo-back.

---

## Phase 1: Present

When the user asks for organization suggestions:

1. **Read existing data** to avoid duplicates:
   ```bash
   python check_duplicates.py --file candidates.txt --new-only
   ```
   This checks against both `rejected_sites.txt` (400+ rejected) and `sites.csv` (active sites).

2. **Only suggest orgs you can verify exist.** Do not fabricate organization names. If unsure whether an org is real, ask the user to name them directly.

3. **Show a numbered list.** That's it. No file changes yet.

**Example:**
```
Here are 10 verified foundations not already in your lists:

1. Freedom House - freedomhouse.org/careers
2. National Endowment for Democracy - ned.org/jobs
3. Open Society Foundations - opensociety.org/careers
4. Democracy Fund - democracyfund.org/jobs
5. Protect Democracy - protectdemocracy.org/careers
...

Which numbers would you like to add?
```

**STOP HERE. Do not write to any files.**

---

## Phase 2: Confirm (Echo-Back Required)

When the user responds (e.g., "add 1, 3, 5"):

**Echo back exactly what you're about to do:**
```
To confirm, I'll add these 3 organizations to sites.csv:

1. Freedom House - freedomhouse.org/careers
3. Open Society Foundations - opensociety.org/careers
5. Protect Democracy - protectdemocracy.org/careers

Proceed?
```

Wait for the user to say yes before touching any files.

---

## Phase 3: Act

Only after confirmation:
1. Append confirmed orgs to `sites.csv`
2. Run `python check_duplicates.py --validate` to verify no conflicts
3. Report what was added

---

## Presentation Formats

### Quick List (5–10 orgs)
```
1. **Organization Name** - careers.example.org
   One-line description (5–10 words)

2. **Another Org** - jobs.example.org
   One-line description
```

### Compact Table (10–20 orgs)
```
| # | Organization              | Focus Area         | URL                        |
|---|---------------------------|--------------------|----------------------------|
| 1 | Freedom House             | Democracy advocacy | freedomhouse.org/careers   |
| 2 | Open Society Foundations  | Justice, democracy | opensociety.org/careers    |
```

### Categorized Groups (20+ orgs)
```
**Democracy & Governance (5)**
1. Freedom House - freedomhouse.org/careers
2. National Endowment for Democracy - ned.org/jobs
...

**Climate & Environment (4)**
6. Natural Resources Defense Council - nrdc.org/careers
...
```

### Key Principles
- Use numbered lists so the user can reference by number
- Bold org names for scanning
- Direct career-page URLs, not homepages
- Group by category when presenting 15+ orgs
- Include count in headers

---

## User Request Formats

When you want to tell the AI to add organizations, use any of these:

### Simple URLs
```
https://example1.org/careers
https://example2.org/jobs
```

### Structured
```
1. Example Foundation
   URL: https://example.org/careers
   Keywords: policy, democracy
```

### Table
```
| Organization      | URL                              | Keywords          |
|-------------------|----------------------------------|-------------------|
| Example Foundation| https://example.org/careers      | policy, democracy |
```

### CSV-Ready
```csv
site_name,url,active,keywords
Example Foundation,https://example.org/careers,yes,policy
```

---

## Validation Commands

### Check individual orgs
```bash
python check_duplicates.py "Org Name 1" "Org Name 2"
```

### Batch check from file
```bash
python check_duplicates.py --file candidates.txt --new-only
```

### Validate sites.csv integrity
```bash
python check_duplicates.py --validate
# or shortcut:
./validate-sites.sh
```

### Output legend
- ✅ **NEW** — Safe to suggest
- ❌ **ALREADY REJECTED** — User said no
- 🔵 **ALREADY ACTIVE** — Already monitoring

---

## Normalization Rules

When comparing names, the validator:
- Converts to lowercase
- Removes "the" prefix
- Strips suffixes: Foundation, Fund, Institute, Inc, LLC, Trust, Philanthropies, Ventures, Collective, Network, Group, Initiative, Project

So "Ford Foundation" = "ford" = "The Ford Fund". Always over-validate.

---

## What This Workflow Prevents

- Suggesting orgs already active or rejected
- Writing to files without user sign-off
- Fabricating organization names that don't exist
- Misaligned numbering between what's presented and what's acted on
