# Managing Your Job Feed From Your Phone

This guide shows you how to manage your job posting aggregator entirely from your phone.

## Initial Setup (One Time)

### Step 1: Enable GitHub Pages

1. Open GitHub on your phone browser
2. Go to your Job-search repository
3. Tap **Settings** (gear icon at top)
4. Scroll down to **Pages** in the left sidebar
5. Under **Source**, select:
   - Source: **GitHub Actions**
6. Save

### Step 2: Enable GitHub Actions

1. In your repository, tap **Actions** tab
2. If prompted, click **I understand my workflows, go ahead and enable them**

### Step 3: Run First Time

1. Go to **Actions** tab
2. Click **Update Job Postings** workflow
3. Click **Run workflow** dropdown
4. Click green **Run workflow** button

Wait 2-3 minutes for it to complete.

### Step 4: Get Your RSS Feed URL

Your RSS feed will be at:
```
https://YOUR-USERNAME.github.io/Job-search/feed.xml
```

Replace `YOUR-USERNAME` with your GitHub username.

Example:
```
https://ZoellerK.github.io/Job-search/feed.xml
```

## Daily Use From Your Phone

### Adding New Job Sites

**Method 1: GitHub Mobile App (Easiest)**
1. Open GitHub app
2. Go to Job-search repository
3. Open `sites.csv` file
4. Tap pencil icon (edit)
5. Add a new line:
   ```
   Company Name,https://company.com/careers,yes,keywords here
   ```
6. Tap **Commit changes**
7. The workflow runs automatically!

**Method 2: GitHub Website**
1. Open github.com in phone browser
2. Navigate to Job-search repository
3. Tap `sites.csv`
4. Tap pencil icon (top right)
5. Add your site
6. Scroll down, tap **Commit changes**

### Viewing Your Jobs

**Option A: RSS Reader App (Recommended)**

Download any RSS reader app:
- **iOS**: NetNewsWire, Reeder, Feedly
- **Android**: Feedly, FeedMe, Inoreader

Subscribe to: `https://YOUR-USERNAME.github.io/Job-search/feed.xml`

**Option B: Web Browser**

Visit: `https://YOUR-USERNAME.github.io/Job-search/`

This shows a nice web page with all your jobs.

## How It Works

1. **You edit sites.csv** from your phone
2. **GitHub Actions automatically runs** the scraper in the cloud
3. **RSS feed updates** at https://YOUR-USERNAME.github.io/Job-search/feed.xml
4. **Your phone RSS reader** shows new jobs

## Automation

The system runs automatically:
- **Daily at 9 AM UTC** (4 AM EST, 1 AM PST)
- **Whenever you edit sites.csv**
- **Manually** (Actions tab → Run workflow)

Change the schedule by editing `.github/workflows/update-jobs.yml` line:
```yaml
- cron: '0 9 * * *'  # Change this
```

[Use crontab.guru](https://crontab.guru/) to customize the schedule.

## Managing Sites

### Add a Site (Get All Jobs)
```csv
Site Name,https://example.com/careers,yes,
```
Leave keywords empty for all jobs.

### Add a Site (Filtered by Keywords)
```csv
Big Company,https://bigco.com/jobs,yes,ESG,sustainability,impact
```

### Disable a Site Temporarily
```csv
Site Name,https://example.com/careers,no,
```
Change `yes` to `no`.

### Remove a Site
Just delete the entire line from sites.csv.

## Troubleshooting

### Feed Not Updating
1. Check **Actions** tab for errors
2. Click the failed workflow to see logs
3. Some sites may block scraping (403 errors)

### Can't Find Feed URL
1. Go to **Settings → Pages**
2. Your URL is shown at the top
3. Add `/feed.xml` to the end

### Jobs Not Appearing
- Some sites block automated access
- Check workflow logs in Actions tab
- Try the `setup_site.py test <url>` command locally to debug

## Tips

- Start with 2-3 sites to test
- Use keywords for large companies
- Leave keywords empty for nonprofits/small companies
- Check your RSS reader daily for new jobs

## Need Help?

- Check workflow logs in Actions tab
- Review the main README.md
- Open an issue in the repository
