# Audio download & sync – up-to-date reference

Use this file when fixing issues or onboarding: **@AUDIO_SYNC_REFERENCE.md**

---

## 1. yt-dlp rename errors (`/tmp/VIDEO_ID.audio.m4a.part` → `...audio.m4a`)

**Problem:** Multiple syncs or phases downloading the same video used shared paths; yt-dlp’s `.part` → rename could fail with "No such file or directory" when another process moved or removed the file.

**Current behavior (canonical code):**

- **File:** `audio_extractor.py`
- **Function:** `download_audio(video_id, work_dir=None, max_retries=2)`
- **Mechanism:**
  - Creates a **unique subdir per call:** `work_dir / f".yt_{uuid.uuid4().hex[:12]}"` (e.g. `/tmp/.yt_abc123def456/`).
  - Passes that dir to yt-dlp via:
    - `-o` template: `dl_dir / f"{video_id}.audio.%(ext)s"`
    - `-P temp:{dl_dir}` and `-P home:{dl_dir}` so temp (`.part`) and final output both live in that dir.
  - Success path returns the file under `dl_dir`; "already exists" check still uses shared `work_dir` for reuse.

**If the error still shows `/tmp/VIDEO_ID.audio.m4a` (no `.yt_*` subdir):**

- Either the **deployed service is running old code** (redeploy), or
- Some other code path is calling yt-dlp without going through `download_audio()` — the only production path is `pipeline.py` → `download_audio()`.

---

## 2. Multiple syncs at once (duplicate POST /sync/async or GET /trigger-sync)

**Problem:** Two syncs could start concurrently and process the same videos, worsening rename races and duplicate work.

**Current behavior (canonical code):**

- **File:** `api.py`
- **Helpers:** `_jobs`, `_jobs_lock`, `_running_sync_job_id()` (returns first running sync job id or `None`).
- **Endpoints:**
  - **POST `/sync/async`** and **GET `/trigger-sync`**: Under `_jobs_lock`, if `_running_sync_job_id()` is non-None, return **202 with that existing job id**; otherwise create a new job, release the lock, call `_run_async_job(job_id, _do_sync, "sync")`, and return 202 with the new job id.

---

## 3. Where to look when fixing things

| Concern              | Primary file         | What to search / check                          |
|----------------------|----------------------|--------------------------------------------------|
| Audio download path  | `audio_extractor.py` | `download_audio`, `dl_dir`, `-o`, `-P`           |
| Sync concurrency     | `api.py`             | `_running_sync_job_id`, `sync_async`, `trigger_sync_get` |
| Pipeline flow        | `pipeline.py`        | `download_audio(video_id, work_dir)`             |
| Other yt-dlp usage   | Repo-wide            | Only production path is `pipeline.py` → `download_audio`; scripts like `test_audio_download_direct.py` are local-only. |

---

## 4. Quick checklist for “something’s still wrong”

- [ ] Deployed image/revision includes the unique-dir and `-P` logic in `audio_extractor.py`.
- [ ] Only one sync runs at a time (check logs for duplicate "sync started" or two 202s for sync in quick succession).
- [ ] Any new code that runs yt-dlp for audio uses `download_audio()` (or replicates its unique-dir + `-P` behavior), not a bare `/tmp/VIDEO_ID` path.

Reference this doc and the listed files when using Claude/Cursor skills to fix missing behavior or deployment drift.
