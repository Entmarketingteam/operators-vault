# Automatic Sync – New Videos Auto-Processed

Set up automatic sync so new YouTube videos are fetched and processed as soon as they're posted.

**👉 RECOMMENDED: Railway Cron Job** (see `RAILWAY_CRON_SETUP.md` for step-by-step guide)

## Option 1: Railway Cron Job (Recommended - Easiest)

Railway supports cron jobs natively. Set one up:

1. **Go to Railway Dashboard:**
   - Your project → **New** → **Cron Job**

2. **Configure:**
   - **Schedule:** `0 */3 * * *` (every 3 hours) or `0 * * * *` (every hour)
   - **Command:** 
     ```bash
     curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync"
     ```
   - If you set `SYNC_TRIGGER_KEY` in Railway Variables, use:
     ```bash
     curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync?key=$SYNC_TRIGGER_KEY"
     ```

3. **Save** – Railway will run this automatically on schedule.

**Why every 3 hours?** YouTube channels typically post 1-2 times per week, so checking every 3 hours catches new videos quickly without hitting API quotas.

## Option 2: n8n Workflow (Already Configured)

The `n8n-workflow-fetch-new.json` workflow is set up to call `/trigger-sync` every 6 hours.

**To activate:**

1. **Set up n8n** (if not already):
   - Deploy n8n or use Railway's n8n template
   - Get `N8N_HOST` and `N8N_API_KEY`

2. **Import and activate workflow:**
   ```bash
   python scripts/setup_n8n_workflows.py
   ```
   This imports the workflow and sets the Railway URL automatically.

3. **Verify in n8n:**
   - Open n8n → Workflows
   - Find "Operators Vault – Sync New Episodes"
   - Ensure it's **Active** (toggle on)
   - Schedule shows: `0 6,12,18,0 * * *` (every 6 hours)

**To change frequency:** Edit the workflow in n8n and update the cron expression:
- Every hour: `0 * * * *`
- Every 3 hours: `0 */3 * * *`
- Every 6 hours: `0 */6 * * *` (current)
- Daily at 9am UTC: `0 9 * * *`

## Option 3: External Cron (GitHub Actions, etc.)

If you prefer external automation:

**GitHub Actions example** (`.github/workflows/sync-vault.yml`):
```yaml
name: Sync Operators Vault
on:
  schedule:
    - cron: '0 */3 * * *'  # Every 3 hours
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger sync
        run: |
          curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync"
```

**Other services:** Use any cron service (cron-job.org, EasyCron, etc.) to call:
```
GET https://superb-smile-production.up.railway.app/trigger-sync
```

## How It Works

1. **Cron triggers** → Calls `GET /trigger-sync`
2. **API returns 202** immediately with `job_id`
3. **Background job runs:**
   - Fetches new videos from YouTube channels (9 Operators, Marketing, Finance, TITANS)
   - Processes all unprocessed videos (download audio → transcribe → extract insights)
4. **Check status:** `GET /jobs/{job_id}` or `GET /stats`

## Monitoring

- **Check sync status:** `GET https://superb-smile-production.up.railway.app/stats`
- **View recent jobs:** Check Railway logs or call `GET /jobs/{job_id}` for the latest job
- **Set up alerts:** Railway can send notifications on job failures

## Recommended Schedule

- **Every 3 hours** (`0 */3 * * *`) – Good balance: catches new videos quickly, doesn't hit API limits
- **Every hour** (`0 * * * *`) – If channels post daily and you want near-real-time
- **Every 6 hours** (`0 */6 * * *`) – Conservative, good for weekly posting schedules

## Security (Optional)

Set `SYNC_TRIGGER_KEY` in Railway → Variables, then cron must call:
```
GET /trigger-sync?key=<your-secret>
```

This prevents unauthorized sync triggers.
