# Quick Reference: Organization Suggestions

## 🚨 MANDATORY CHECKS BEFORE SUGGESTING ORGANIZATIONS

### Pre-Suggestion Checklist

- [ ] Read `rejected_sites.txt` (400+ rejected orgs)
- [ ] Read `sites.csv` (66+ active sites)
- [ ] Validate ALL candidates with `check_duplicates.py`
- [ ] Filter to only NEW organizations
- [ ] Present validated results to user

## Quick Commands

### Validate a Few Organizations
```bash
python check_duplicates.py "Org 1" "Org 2" "Org 3"
```

### Validate Many Organizations (File Input)
```bash
# Create file with candidates (one per line)
# Then run:
python check_duplicates.py --file candidates.txt --new-only
```

### Check Sites.csv Validity
```bash
./validate-sites.sh
```

## Symbol Legend

- ✅ **NEW** - Safe to suggest (not in active or rejected)
- ❌ **ALREADY REJECTED** - User said no, don't suggest
- 🔵 **ALREADY ACTIVE** - Already monitoring, don't suggest

## File Locations

- **Rejected List**: `rejected_sites.txt` (400+ organizations)
- **Active Sites**: `sites.csv` (66+ organizations)
- **Validator**: `check_duplicates.py`
- **Quick Validate**: `./validate-sites.sh`

## Golden Rule

**NEVER suggest an organization without first validating it against rejected_sites.txt and sites.csv**

When in doubt, always check first!
