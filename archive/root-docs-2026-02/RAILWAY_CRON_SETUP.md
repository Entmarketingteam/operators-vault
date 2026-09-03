> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Railway Cron Job Setup - Automatic Sync

**Quick setup guide to automatically sync new YouTube videos every 3 hours.**

---

## Option A: One-Click Script (recommended if you have Railway API token)

From the repo root, with `RAILWAY_API_TOKEN` in `.env` or **Doppler** (and after running `railway link` once):

```bash
python scripts/create_railway_cron_service.py
```

If the token is in Doppler, use:

```bash
doppler run -- python scripts/create_railway_cron_service.py
```

This creates a **vault-sync-cron** service (Docker image `curlimages/curl`), sets `TRIGGER_URL`, and configures cron to run every 3 hours. If the API shape differs, the script prints manual steps.

Optional env: `RAILWAY_APP_URL` (default `https://superb-smile-production.up.railway.app`), `SYNC_TRIGGER_KEY` (appended to URL if set).

---

## Option B: Deploy Cron Runner from Repo

1. **Railway Dashboard** → your project → **New** → **GitHub Repo**
2. Select this repo; set **Root Directory** to `cron-runner`
3. Add variable: **TRIGGER_URL** = `https://superb-smile-production.up.railway.app/trigger-sync` (or your app URL + `/trigger-sync`; if you use `SYNC_TRIGGER_KEY`, add `?key=YOUR_KEY`)
4. Deploy. The `cron-runner/railway.json` sets **Cron Schedule** to `0 */3 * * *` (every 3 hours)

---

## Option C: Manual Cron Job in Dashboard

### 1. Go to Railway Dashboard
- Open: https://railway.app
- Navigate to your **operators-vault** project

### 2. Create Cron Job
- Click **"New"** → **"Cron Job"**

### 3. Configure the Cron Job

**Schedule:**
```
0 */3 * * *
```
This runs every 3 hours (at :00, :03, :06, :09, :12, :15, :18, :21).

**Other options:**
- Every hour: `0 * * * *`
- Every 6 hours: `0 */6 * * *`
- Daily at 9am UTC: `0 9 * * *`

**Command:**
```bash
curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync"
```

**If you set `SYNC_TRIGGER_KEY` in Railway Variables:**
```bash
curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync?key=$SYNC_TRIGGER_KEY"
```

### 4. Save and activate (Option C)
- Click **"Save"** or **"Deploy"**
- The cron job will start running automatically

## Verify It's Working

### Test manually:
```bash
curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync"
```

You should get:
```json
{
  "job_id": "uuid-here",
  "status": "running",
  "type": "sync",
  "jobs": "/jobs/uuid-here"
}
```

### Check sync status:
```bash
curl "https://superb-smile-production.up.railway.app/stats"
```

### View logs:
- Railway Dashboard → Your Cron Job → **Logs** tab
- You'll see when sync runs and any errors

## What Happens Automatically

1. **Every 3 hours**, Railway calls `/trigger-sync`
2. **API returns 202** immediately (no timeout)
3. **Background job:**
   - Fetches new videos from YouTube channels (9 Operators, Marketing, Finance, TITANS)
   - Processes all unprocessed videos:
     - Downloads audio
     - Transcribes with Deepgram
     - Extracts insights with Anthropic
     - Stores in Supabase
4. **New videos appear** in your vault automatically!

## Monitoring

- **Railway Dashboard** → Cron Job → Logs (see execution history)
- **API Stats:** `GET /stats` shows video counts per podcast
- **Job Status:** `GET /jobs/{job_id}` for specific sync status

## Troubleshooting

**Cron job not running?**
- Check Railway → Cron Job → Logs for errors
- Verify the URL is correct
- Ensure Railway service is running (`GET /health`)

**Sync not finding new videos?**
- Check `YOUTUBE_API_KEY` is set in Railway Variables
- Verify channel handles are correct (9operators, marketing_operator, finance_operators)
- Check YouTube API quota hasn't been exceeded

**Videos not processing?**
- Check `DEEPGRAM_API_KEY` and `ANTHROPIC_API_KEY` are set
- View Railway service logs for processing errors
- Check `GET /stats` to see how many are unprocessed

## Security (Optional)

To prevent unauthorized sync triggers:

1. **Set `SYNC_TRIGGER_KEY` in Railway Variables:**
   - Railway → Your Service → Variables
   - Add: `SYNC_TRIGGER_KEY` = `your-secret-key-here`

2. **Update cron command:**
   ```bash
   curl -X GET "https://superb-smile-production.up.railway.app/trigger-sync?key=$SYNC_TRIGGER_KEY"
   ```

Now only requests with the correct key will trigger sync.
