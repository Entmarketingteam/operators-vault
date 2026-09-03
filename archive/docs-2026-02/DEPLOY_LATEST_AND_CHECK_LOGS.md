> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Deploy latest from GitHub and fix from logs

## What was done

1. **Pushed latest to GitHub** – Version bump to 1.0.1 (commit `e0294dd`) so the repo has the diagnostic code:
   - `BOOT SHA: <RAILWAY_GIT_COMMIT_SHA>` at startup
   - `[audio] download_audio v2 called for <video_id>` at start of each download
   - `[audio] download failed for <video_id>: err='...'` (single line with the real error)

2. **Triggered Railway redeploy** – `python scripts/redeploy_railway.py` was run so superb-smile rebuilds.

## Make sure the service builds from GitHub (required)

The latest logs still show the old format (no BOOT SHA, no `err=`). So the running app is an older build. Do this so the new code runs:

1. **Railway Dashboard** → **operators-vault** project → click **superb-smile**.
2. Open **Settings** (or the **Source** / **Connect** area).
3. Under **Source**, if it’s not already **GitHub**:
   - Click **Connect Repo** (or **Change Source**).
   - Choose **GitHub** and the **Entmarketingteam/operators-vault** repo.
   - Set branch to **master** (or your default branch).
4. **Trigger a new deploy** from GitHub:
   - Go to **Deployments** and click **Deploy** / **Redeploy** (or push a new commit to `master`; if the repo is connected, it will build from the latest commit).
5. Wait for the new deployment to show **Active** / **Completed**, then check **Logs**. You should see:
   - `BOOT SHA: e0294dd...` (or the latest commit SHA).
   Then trigger a sync and look for `[audio] download failed for ... err='...'`.

## After the new deployment is live

1. **Check startup log** – In superb-smile **Logs**, near the top you should see:
   ```text
   BOOT SHA: e0294dd...
   ```
   If you see that, the new code is running.

2. **Trigger a sync** (or wait for the cron):
   ```bash
   curl -X POST https://superb-smile-production.up.railway.app/sync/async
   ```

3. **Check logs for the real error** – In the same **Logs** stream, look for:
   - `[audio] download_audio v2 called for ...` (confirms new code path)
   - `[audio] download failed for <video_id>: err='...'` – the quoted string is the actual failure (e.g. `'yt-dlp or ffmpeg not found'`, `'exit 1: HTTP 403'`, etc.)

4. **Fix from there** – Once you have the exact `err=` message we can fix the root cause (ffmpeg, YouTube block, proxy, etc.).

## Quick test from repo

```bash
# Trigger sync and get job id
curl -sS -X POST https://superb-smile-production.up.railway.app/sync/async

# Then open Railway Dashboard → superb-smile → Logs and look for BOOT SHA, v2, err=
```
