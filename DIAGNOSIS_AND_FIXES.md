# End-to-End Diagnosis and Fixes

## Issues Identified

### 1. Cron Service Failure
**Problem:** `vault-sync-cron` service failed 20 minutes ago with error: `curl: (3) URL rejected: Bad hostname`

**Root Cause:** 
- TRIGGER_URL was pointing to GET `/trigger-sync` which returns 404
- Should use POST `/sync/async` instead

**Fix Applied:**
- Updated TRIGGER_URL to: `https://superb-smile-production.up.railway.app/sync/async`
- Updated start command to use POST instead of GET

**Manual Fix (if script fails):**
1. Railway Dashboard → `vault-sync-cron` → Variables
2. Set `TRIGGER_URL` = `https://superb-smile-production.up.railway.app/sync/async`
3. Settings → Start Command = `curl -sS -X POST "$TRIGGER_URL"`

### 2. Video Processing Failure (0 videos processed)
**Problem:** All 26 videos fetched but 0 processed. Every audio download fails.

**Root Cause:** 
- YouTube is blocking Railway's cloud IP addresses (most likely)
- This is common with datacenter IPs - YouTube blocks/throttles them

**Evidence:**
- All videos fail immediately with `[audio] download failed`
- No specific error messages visible (need to check Railway logs after latest deploy)
- Pattern consistent across all videos

**Solutions:**

#### Option A: Process Locally (Recommended)
Use your local machine to process videos (bypasses IP blocking):

```bash
# 1. Install dependencies
pip install yt-dlp

# 2. Install ffmpeg (system dependency)
# Windows: Download from https://ffmpeg.org/download.html
# Mac: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg

# 3. Set DATABASE_URL in .env to your Supabase connection string

# 4. Run local processor
python local_process_videos.py --process-new
```

This uses your home IP instead of Railway's cloud IP, so YouTube won't block it.

#### Option B: Check Railway Logs for Detailed Errors
After the latest deploy, check Railway logs for messages like:
- `[audio] ERROR: exit 1: HTTP 403 Forbidden`
- `[audio] ERROR: exit 1: Video unavailable`
- `[audio] yt-dlp output: ...` (full error details)

This will confirm if it's YouTube blocking or another issue.

#### Option C: Use Different Worker
Run processing on a different cloud provider or VM that isn't blocked by YouTube.

### 3. Error Messages Not Captured
**Problem:** API returns `errors: []` even though processing fails.

**Fix Applied:**
- Updated `_do_sync()` and `_do_process_new()` to capture errors when `_process_one()` returns `False`
- Added stderr logging for better visibility
- Errors now included in API response

## Testing

Run diagnostics:
```bash
python scripts/diagnose_issues.py
```

This will:
1. Check cron service configuration
2. Test audio download locally (if yt-dlp installed)
3. Test Railway endpoint connectivity
4. Provide recommended solutions

## Next Steps

1. **Wait for cron service to run** (every 3 hours) or trigger manually:
   ```bash
   curl -X POST https://superb-smile-production.up.railway.app/sync/async
   ```

2. **Check Railway logs** after next sync to see detailed error messages

3. **If all videos still fail**, process locally:
   ```bash
   python local_process_videos.py --process-new
   ```

4. **Monitor cron service** - should now work with POST `/sync/async`

## Files Created

- `scripts/diagnose_issues.py` - Comprehensive diagnostics
- `scripts/fix_all_issues.py` - Automated fixes
- `local_process_videos.py` - Local video processor (bypasses IP blocking)

## Code for Alternative Processing

If you need to run processing elsewhere, use `local_process_videos.py` or copy the processing logic:

```python
# Core processing code is in pipeline.py
from pipeline import _process_one, _get_unprocessed
import psycopg2

# Connect to database
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get unprocessed videos
rows = _get_unprocessed(cur)

# Process each
for video_id, podcast in rows:
    success = _process_one(video_id, podcast)
    if success:
        print(f"Processed: {video_id}")
    else:
        print(f"Failed: {video_id}")

conn.close()
```
