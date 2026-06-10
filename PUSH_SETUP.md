# Push Notifications & Auto-Sweep Setup

The daily workflow now does three new things:

1. **Filters out junk** — navigation links, donate pages, and articles no
   longer appear in the feed, dashboard, or digest.
2. **Sweeps ATS platforms** — runs your Q1/Q2/Q3 keyword searches across
   13 ATS platforms (Greenhouse, Lever, Workday, …) automatically via
   Google's official search API. This replaces the manual daily click-through
   in the ATS Sweep dashboard.
3. **Pushes you a daily digest** — when new jobs are found, a GitHub issue
   titled "Job digest — YYYY-MM-DD" is created with everything new, sorted
   by relevance. With the GitHub mobile app installed, that's a push
   notification on your phone.

The junk filter and digest work **immediately with no setup**. The ATS sweep
needs a free Google API key (~10 minutes, steps below).

---

## Step 1 — Create the search engine (gives you the "CX" ID)

1. Open <https://programmablesearchengine.google.com/> and sign in with any
   Google account.
2. Click **Add** to create a new search engine.
   - Name: anything, e.g. `Job Sweep`
   - Under "What to search": choose **Search the entire web**
3. Click **Create**, then open the engine's **Overview** page and copy the
   **Search engine ID** (a string like `a1b2c3d4e5f6g7h8i`). This is your `CX`.

## Step 2 — Get the API key

1. Open <https://developers.google.com/custom-search/v1/overview>
2. Scroll to "API key" and click **Get a key**.
3. Pick "Create a new project", name it anything (e.g. `job-search`),
   and copy the key it shows you.

The free tier allows **100 searches per day**. The sweep uses ~39
(13 platforms × 3 queries), so there is no cost.

## Step 3 — Add both as repository secrets

1. On GitHub, open this repository → **Settings** → **Secrets and
   variables** → **Actions** → **New repository secret**.
2. Add two secrets:
   - Name `GOOGLE_PSE_API_KEY`, value = the API key from Step 2
   - Name `GOOGLE_PSE_CX`, value = the Search engine ID from Step 1

That's it. The next daily run (9 AM UTC) will include sweep results. You can
trigger a run right away from the **Actions** tab → "Update Job Postings" →
**Run workflow**.

## Step 4 — Make sure the digest reaches your phone

- Install the **GitHub mobile app** and sign in.
- On this repository, tap **Watch → All Activity** so new issues notify you.
- Each day with new jobs you'll get one notification; open the issue to read
  the digest. Close the issue when you're done (or don't — it doesn't matter).

### Optional: direct phone push without the GitHub app (ntfy)

1. Install the free **ntfy** app (iOS/Android).
2. In the app, subscribe to a topic with a hard-to-guess name, e.g.
   `kz-jobs-x7k2m9`.
3. Add a repository secret named `NTFY_TOPIC` with that topic name.

You'll then also get a native push notification listing the top new jobs.

---

## Tuning the sweep (no code required)

Everything lives in `config.json` under `"sweep"`:

- `queries` — the three keyword groups (edit terms freely)
- `platforms` — which ATS sites to sweep
- `date_restrict` — how far back Google looks (`d2` = 2 days)
- `enabled` — set to `false` to turn the sweep off

## Testing locally

```bash
python job_aggregator.py digest 48   # build digest.md from the last 48h
GOOGLE_PSE_API_KEY=... GOOGLE_PSE_CX=... python job_aggregator.py sweep
```
