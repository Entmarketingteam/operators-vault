# Video Processing Fix

## Problem Identified

Videos were being fetched successfully (35 videos in DB) but **0 videos were processed**. The processing jobs completed but returned `processed: 0`.

## Root Cause

**Missing `ffmpeg` dependency on Railway.** 

- `yt-dlp` (in `requirements.txt`) is installed via pip ✅
- But `ffmpeg` is a **system dependency** that must be installed separately ❌
- Railway uses **Nixpacks** builder, which doesn't include ffmpeg by default
- When `_process_one()` tries to download audio, `yt-dlp` fails because `ffmpeg` isn't available
- Errors were being swallowed silently (no exception handling)

## Fixes Applied

### 1. Added `nixpacks.toml`
Created `nixpacks.toml` to install `ffmpeg` during Railway builds:
```toml
[phases.setup]
nixPkgs = ["ffmpeg"]
```

### 2. Added Error Handling
Updated `_do_sync()` and `_do_process_new()` in `api.py` to:
- Catch exceptions from `_process_one()` 
- Log error messages to Railway logs
- Include errors in job result (first 5 errors)

This will help diagnose issues if processing still fails after ffmpeg is installed.

## Next Steps

1. **Commit and push these changes:**
   ```bash
   git add nixpacks.toml api.py PROCESSING_FIX.md
   git commit -m "Fix video processing: add ffmpeg to Railway build and error handling"
   git push
   ```

2. **Railway will auto-deploy** (or manually redeploy if needed)

3. **After deploy completes, trigger processing:**
   ```bash
   python scripts/trigger_sync.py
   ```
   Or call: `GET https://superb-smile-production.up.railway.app/trigger-sync`

4. **Check Railway logs** for:
   - `[audio] download failed: ...` messages (should be gone if ffmpeg fix worked)
   - `[ERROR] Processing failed: ...` messages (will show actual errors if any)
   - `[done]` messages (successful processing)

5. **Monitor job status:**
   - `GET https://superb-smile-production.up.railway.app/jobs/{job_id}`
   - Should see `processed > 0` after ffmpeg is installed

## Expected Behavior After Fix

- Videos will download audio successfully (ffmpeg available)
- Transcriptions will be created (Deepgram)
- Insights will be extracted (Anthropic)
- Videos will be marked as processed in DB
- Stats endpoint will show `processed > 0`

## If Processing Still Fails

Check Railway logs for the actual error. Common remaining issues:

1. **YouTube blocking Railway IPs** (HTTP 403/429)
   - Solution: Process videos locally (see `docs/TROUBLESHOOTING_AUDIO_DOWNLOAD.md`)

2. **Deepgram/Anthropic API errors**
   - Check API keys are set correctly
   - Check API quotas/limits

3. **Database connection issues**
   - Verify `DATABASE_URL` is correct
   - Check Supabase connection limits

## Automatic Processing Going Forward

Once fixed, the cron job (`vault-sync-cron`) will:
- Run every 3 hours
- Call `/trigger-sync` which:
  - Fetches new videos from YouTube ✅
  - Processes all unprocessed videos ✅
- New videos will be automatically processed within 3 hours of being posted
