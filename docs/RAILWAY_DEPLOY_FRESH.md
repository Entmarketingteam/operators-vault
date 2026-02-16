# Railway: Stuck cron + stale main deploy

## Delete cron and recreate (stuck run still going)

If the long-running cron execution still shows "Running" after redeploying the cron service:

1. **Delete the cron service** (this removes the service and all its runs):
   ```bash
   python scripts/delete_cron_service.py
   ```
   If that fails (e.g. 401/400), delete manually: Railway Dashboard → **vault-sync-cron** → Settings → Danger → **Remove Service**.

2. **Recreate the cron** (new service, correct URL):
   ```bash
   python scripts/create_railway_cron_service.py
   ```
   The create script now uses **POST /sync/async** (not /trigger-sync), so the new cron will trigger syncs correctly.

## What was done earlier

1. **Cron redeploy** – `python scripts/redeploy_cron.py` was run (may not stop a stuck run; use delete + recreate above if it’s still running).

2. **Main service redeploy** – `python scripts/redeploy_railway.py` was run to trigger a new deploy of **superb-smile**.

## If superb-smile still shows “last week via CLI”

Then the **new logging (BOOT SHA, v2, err=)** may not be live. To get the latest code:

1. In Railway → **superb-smile** → **Settings** (or **Source**):
   - Ensure the service is connected to **GitHub** and the correct repo/branch (e.g. `master`).
2. Trigger a deploy from the **latest commit**:
   - Either push a small commit and let Railway auto-deploy, or  
   - Use **Deployments** → **Deploy** / **Redeploy** and confirm the build uses the **GitHub** source (not an old CLI upload).

After a deploy that uses the latest GitHub commit, logs should show:
- `BOOT SHA: <commit_sha>`
- `[audio] download_audio v2 called for <video_id>`
- `[audio] download failed for <video_id>: err='...'`

## Stopping a stuck cron run later

Run:
```bash
python scripts/redeploy_cron.py
```
That redeploys the cron service and ends any run that’s stuck “Running”.
