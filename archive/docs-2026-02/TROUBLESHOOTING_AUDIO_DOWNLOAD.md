> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Troubleshooting: Audio download failed on Railway

If sync runs and **fetch-new** succeeds (videos upserted) but every video shows **`[audio] download failed`**, the pipeline never gets transcriptions or insights. This doc explains likely causes and workarounds.

---

## 1. See the real error (after latest deploy)

The app now logs **why** each download failed. After deploying:

- Trigger a sync (e.g. POST /sync or wait for n8n).
- In Railway logs, look for lines like:  
  **`[audio] download failed: exit 1: Unable to extract...`** or **`yt-dlp or ffmpeg not found`**.

That message tells you which case below applies.

---

## 2. Common causes

### A. YouTube blocking or throttling cloud IPs

YouTube often blocks or rate-limits requests from datacenter IPs (e.g. Railway, AWS, GCP). So:

- **Same video** may work when you run `python pipeline.py --process <video_id>` from your laptop, but fail when sync runs on Railway.
- Typical yt-dlp errors: HTTP 403, 429, "Video unavailable", "Unable to extract uploader id", or similar.

**Workarounds:**

1. **Run processing from your machine (recommended for now)**  
   - Keep **fetch-new** on Railway (so the `videos` table stays up to date).  
   - Run **processing** locally so downloads use your home IP:
     - Set `DATABASE_URL` in `.env` to the same Supabase URL as Railway (use the **Session pooler** if Direct connection fails from your network).
     - Run: `python pipeline.py --fetch-new` (optional, to pull new videos into DB), then `python pipeline.py --process-new` to process all unprocessed videos.  
   - After processing, transcriptions and insights are in the DB; search will work.

2. **Use a different worker**  
   - Run the download+transcribe step on a machine or VM that has a residential or non-blocked IP (e.g. a home server or a different provider that isn’t heavily blocked by YouTube). Point `DATABASE_URL` at the same Supabase DB.

3. **Proxy (use with care)**  
   - Some teams use an outbound proxy for yt-dlp so requests come from a different IP. That can violate YouTube’s ToS; only consider if you understand the risks.

### B. ffmpeg not installed on Railway

yt-dlp uses **ffmpeg** for `--extract-audio`. If the Railway runtime doesn’t include ffmpeg, you’ll see errors like "ffmpeg not found" or "Executable not found".

**Fix:**

- Add ffmpeg to your Railway build. Options:
  - **Nixpacks:** add a `nixpacks.toml` or set `NIXPACKS_PKGS=ffmpeg` (if your stack supports it).
  - **Dockerfile:** use an image that has ffmpeg (e.g. `python:3.11` plus `apt-get install -y ffmpeg`), or a base like `python:3.11-slim` and install ffmpeg in the Dockerfile.
- Redeploy and check logs again; the error message should change if ffmpeg was the only issue.

### C. yt-dlp not found

If the log says **"yt-dlp or ffmpeg not found"** and names one of them, ensure that executable is in the PATH in the Railway environment. yt-dlp is installed via `requirements.txt` (pip); ffmpeg is a system dependency and must be installed separately (see B).

---

## 3. Summary

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| Every download fails; log says HTTP 403/429 or "unavailable" | YouTube blocking cloud IP | Run `pipeline.py --process-new` locally with same `DATABASE_URL`; keep fetch-new on Railway. |
| "ffmpeg not found" / "Executable not found" | ffmpeg missing on Railway | Add ffmpeg to Railway build (Nixpacks or Dockerfile). |
| "yt-dlp not found" | yt-dlp not in PATH | Ensure requirements.txt is installed and the process runs in an env where `yt-dlp` is on PATH. |

After the next deploy, the first failure line for each video will include the short error message so you can confirm which case you’re in.
