# Sites Validation Guide

## Overview

This project includes automated validation to ensure that sites in `sites.csv` are checked against the `rejected_sites.txt` exclusion list. This prevents accidentally adding sites that have already been rejected.

## Validation Rules

The validation system checks that:
1. No **active** sites in `sites.csv` appear in `rejected_sites.txt`
2. Both exact name matches and normalized name matches are checked
3. Normalization removes common suffixes like "Foundation", "Fund", "Institute", etc.

## How to Use

### 1. Quick Validation (Recommended)

Before committing changes to `sites.csv`, run:

```bash
./validate-sites.sh
```

Or directly:

```bash
python check_duplicates.py --validate
```

### 2. Check New Site Suggestions

#### Individual Organizations
To check if new organizations are safe to add:

```bash
python check_duplicates.py "Organization Name 1" "Organization Name 2"
```

Example:
```bash
python check_duplicates.py "Ford Foundation" "Open Society Foundations"
```

#### Batch Check from File
For checking many organizations at once, create a text file with one organization per line:

```bash
cat > suggestions.txt << EOF
Organization Name 1
Organization Name 2
Organization Name 3
EOF

python check_duplicates.py --file suggestions.txt
```

#### Filter to Show Only New Organizations
Use `--new-only` to see only organizations that are safe to add:

```bash
python check_duplicates.py --file suggestions.txt --new-only
```

Output will show:
- ✅ **NEW** - Safe to suggest (not in active or rejected lists)
- 🔵 **ALREADY ACTIVE** - Already in sites.csv
- ❌ **ALREADY REJECTED** - In rejected_sites.txt

### 3. Automated GitHub Actions Validation

The validation runs automatically on:
- Every push that modifies `sites.csv`, `rejected_sites.txt`, or `check_duplicates.py`
- Every pull request with these file changes
- Manual workflow dispatch

**If validation fails**, the GitHub Actions workflow will fail and show which sites violate the rule.

## Setting Up Pre-Commit Hook (Optional)

To automatically validate before every commit:

1. Create `.git/hooks/pre-commit`:
```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Check if sites.csv was modified
if git diff --cached --name-only | grep -q "sites.csv"; then
    echo "Validating sites.csv against rejected list..."
    python check_duplicates.py --validate
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Commit blocked: Active sites found in rejected list"
        echo "Please remove or mark these sites as inactive before committing"
        exit 1
    fi
fi
EOF
```

2. Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Available Options

### Command-Line Flags

- `--validate` - Validate that no active sites in sites.csv are in rejected_sites.txt
- `--file <filename>` - Read organization names from a file (one per line)
- `--new-only` - Show only NEW organizations (filter out active/rejected)

### Usage Examples

```bash
# Validate sites.csv
python check_duplicates.py --validate

# Check individual organizations
python check_duplicates.py "Org 1" "Org 2"

# Check organizations from file
python check_duplicates.py --file candidates.txt

# Show only new organizations from file
python check_duplicates.py --file candidates.txt --new-only
```

## What Happens When Validation Fails?

If validation fails, you'll see output like:

```
❌ VALIDATION FAILED: Found active sites in rejected list:
================================================================================
  ❌ Human Rights Watch (matches rejected: human rights watch)
  ❌ Ford Foundation (exact match in rejected list)
================================================================================

Total violations: 2

Please remove these sites from sites.csv or mark them as inactive.
```

### To Fix:

1. **Remove the site** from `sites.csv`, or
2. **Mark it as inactive** by changing `active` column to `no`

## File Structure

- `check_duplicates.py` - Main validation script
- `validate-sites.sh` - Quick validation wrapper
- `sites.csv` - Active sites list
- `rejected_sites.txt` - Exclusion list
- `.github/workflows/validate-sites.yml` - GitHub Actions workflow

## Best Practices

1. **Always check before adding new sites**: Run `python check_duplicates.py "Site Name"` first
2. **Validate locally before pushing**: Run `./validate-sites.sh`
3. **Document rejections**: When rejecting a site, add it to `rejected_sites.txt` with a category
4. **Keep normalized names in mind**: "Ford Foundation" matches "Ford Fund" due to normalization

## Normalization Rules

The following transformations are applied when comparing names:
- Convert to lowercase
- Remove "the" prefix
- Remove suffixes: Foundation, Fund, Institute, Inc, LLC, Trust, Philanthropies, Ventures, Collective, Network, Group, Initiative, Project

Example matches:
- "Ford Foundation" = "ford"
- "The Gates Fund" = "gates"
- "MacArthur Foundation" = "macarthur"
