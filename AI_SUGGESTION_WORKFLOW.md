# AI Assistant Organization Suggestion Workflow

## CRITICAL RULE FOR AI ASSISTANTS

**When asked to suggest organizations/foundations to add to the RSS feed, you MUST:**

1. **READ `rejected_sites.txt`** - Check what has been rejected before
2. **READ `sites.csv`** - Check what is already active
3. **VALIDATE ALL SUGGESTIONS** - Use `check_duplicates.py` to verify each suggestion
4. **ONLY PRESENT NEW ORGANIZATIONS** - Filter out any that are already active or rejected

## Workflow Steps

### Step 1: Generate Candidate List
When the user requests organization suggestions (e.g., "give me 20 foundations to consider"), generate a list of potential candidates based on the criteria.

### Step 2: Read Existing Data
```bash
# Always read these files first
cat rejected_sites.txt
cat sites.csv
```

### Step 3: Validate Candidates
Use the check_duplicates.py script to validate ALL candidates:

```bash
python check_duplicates.py "Org Name 1" "Org Name 2" "Org Name 3" ...
```

Or use the batch validation approach for many organizations.

### Step 4: Filter Results
- ❌ **EXCLUDE** any marked as "ALREADY REJECTED"
- ❌ **EXCLUDE** any marked as "ALREADY ACTIVE"
- ✅ **INCLUDE** only those marked as "NEW - Safe to suggest"

### Step 5: Present to User
Only show the filtered list of NEW organizations that have passed validation.

## Example Interaction

**WRONG Way:**
```
User: "Give me 20 foundations to consider"
AI: [Generates 20 suggestions without checking]
AI: "Here are 20 foundations..."
User: "But you suggested Human Rights Watch, I already rejected that!"
```

**CORRECT Way:**
```
User: "Give me 20 foundations to consider"
AI: Let me check what's already been rejected or added...
AI: [Reads rejected_sites.txt - sees 400+ rejected organizations]
AI: [Reads sites.csv - sees 66+ active sites]
AI: [Generates 50 candidate organizations based on relevant criteria]
AI: [Creates temporary file with candidates]
AI: [Runs: python check_duplicates.py --file candidates.txt --new-only]
AI: [Receives 25 NEW organizations after filtering]
AI: [Presents top 20 NEW organizations to user]
User: "Perfect, these are all new!"
```

## Detailed Step-by-Step Process

### Complete Example Workflow

```bash
# Step 1: Generate candidate list (example: 50 candidates)
cat > candidates.txt << EOF
Acumen Fund
Ashoka
Bill & Melinda Gates Foundation
...
EOF

# Step 2: Validate against existing data
python check_duplicates.py --file candidates.txt --new-only

# Step 3: Review output - only shows NEW organizations
# Output shows only organizations not in rejected_sites.txt or sites.csv

# Step 4: Present filtered results to user
```

### Practical AI Assistant Commands

When the user asks for suggestions, execute these commands:

```bash
# 1. Quick check of existing data size
wc -l rejected_sites.txt sites.csv

# 2. Validate your candidate list
python check_duplicates.py --file my_suggestions.txt --new-only

# 3. Only present organizations marked as "NEW - Safe to suggest"
```

## Batch Validation Commands

### Method 1: Command Line Arguments
For validating a few organizations:

```bash
python check_duplicates.py "Foundation Name 1" "Foundation Name 2" "Foundation Name 3"
```

### Method 2: File Input (Recommended for 10+ organizations)
Create a file with one organization per line:

```bash
# Create suggestions file
cat > candidates.txt << EOF
American Civil Liberties Union
Electronic Frontier Foundation
Freedom of the Press Foundation
EOF

# Validate all at once
python check_duplicates.py --file candidates.txt
```

### Method 3: Filter to Show Only NEW Organizations
Use `--new-only` to filter out duplicates and only show new suggestions:

```bash
python check_duplicates.py --file candidates.txt --new-only
```

This will:
- ✅ Show only NEW organizations
- Hide organizations already active or rejected
- Display count of filtered organizations

## What This Prevents

✅ Suggesting organizations already in `sites.csv` (waste of time)
✅ Suggesting organizations in `rejected_sites.txt` (user already said no)
✅ Having to manually cross-reference lists
✅ User frustration from redundant suggestions

## Files to Always Check

1. **`rejected_sites.txt`** - 400+ organizations manually rejected by user
2. **`sites.csv`** - 66+ organizations currently being monitored
3. **Use `check_duplicates.py`** - Handles name normalization automatically

## Implementation Notes

- The validation handles name variations (e.g., "Ford Foundation" vs "Ford Fund")
- Normalization removes common suffixes automatically
- Always over-validate rather than under-validate
- When in doubt, check before suggesting
