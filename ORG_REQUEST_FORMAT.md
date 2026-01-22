# How to Request Adding Organizations

When you want me to add new organizations to the job search system, use one of these clean formats:

---

## Format 1: Simple List (Recommended for Quick Additions)

Just provide the URLs, one per line:

```
https://example1.org/careers
https://example2.org/jobs
https://foundation3.org/opportunities
```

I'll auto-detect the organization name and job listings.

---

## Format 2: Structured List (For Better Control)

Use this format when you want to specify names and keywords:

```
1. Example Foundation
   URL: https://example.org/careers
   Keywords: policy, democracy

2. Another Organization
   URL: https://another.org/jobs
   Keywords: ukraine, international

3. Third Org
   URL: https://third.org/opportunities
   Keywords: philanthropy, nonprofit
```

---

## Format 3: Table Format (Best for Many Organizations)

For bulk additions, use markdown table format:

```
| Organization Name          | URL                                    | Keywords              |
|----------------------------|----------------------------------------|-----------------------|
| Example Foundation         | https://example.org/careers            | policy, democracy     |
| Another Organization       | https://another.org/jobs               | ukraine, international|
| Third Org                  | https://third.org/opportunities        | philanthropy, nonprofit|
```

---

## Format 4: CSV-Ready (For Direct Import)

Provide data in CSV format for immediate import:

```csv
site_name,url,active,keywords
Example Foundation,https://example.org/careers,yes,policy
Another Organization,https://another.org/jobs,yes,ukraine
Third Org,https://third.org/opportunities,yes,philanthropy
```

---

## Tips for Clean Requests

✅ **DO:**
- Group related organizations together
- Include full URLs (with https://)
- Use career/jobs page URLs (not homepage)
- Add keywords if you know them (optional)
- Number your list if using structured format

❌ **DON'T:**
- Mix different formats in one request
- Include duplicate organizations
- Use shortened URLs
- Include broken/incomplete URLs

---

## Example Request

**Good:**
> "Add these 5 foundations:
>
> https://example1.org/careers
> https://example2.org/jobs
> https://example3.org/opportunities
> https://example4.org/work-with-us
> https://example5.org/team/jobs"

**Better:**
> "Add these democracy organizations:
>
> | Organization          | URL                              | Keywords          |
> |-----------------------|----------------------------------|-------------------|
> | Democracy Fund        | https://democracy.org/careers    | policy, grants    |
> | Freedom House         | https://freedom.org/jobs         | democracy, rights |
> | Open Society          | https://opensociety.org/careers  | global, advocacy  |"

---

## What Happens Next

1. I'll validate all URLs
2. Auto-detect job listings where possible
3. Add successfully detected sites to `sites.csv`
4. Report any sites that need custom configuration
5. Show summary of what was added

You can then commit the changes to the repository when ready.
