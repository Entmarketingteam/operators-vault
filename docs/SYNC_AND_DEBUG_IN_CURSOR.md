# Keep local, GitHub, and Railway in sync — debug in Cursor

**Goal:** One source of truth (this repo). Local = GitHub. Railway deploys from GitHub. All fixes and agent changes live in the repo so debugging stays in Cursor.

---

## 1. You (and the agent) keep things in sync

**Before debugging or making changes**
- Pull so your local branch matches GitHub:
  ```bash
  git pull origin master
  ```

**After the agent (or you) changes code**
- Commit and push so GitHub (and Railway) have the latest:
  ```bash
  git add -A
  git commit -m "Short description of the fix"
  git push origin master
  ```
- Railway will redeploy from the push. Give it a minute, then test.

**Why this helps**
- If you troubleshoot "outside Cursor," any fixes you make elsewhere won’t be in this repo unless you bring them back. If we always commit and push from Cursor, the repo stays the single source of truth and debugging can stay in Cursor.

---

## 2. Fast cloud debug loop (from Cursor or terminal)

1. **Pick one video** (e.g. a known failing or unprocessed `video_id` from your DB).
2. **Run one video on Railway:**
   ```bash
   curl -sS -X POST https://superb-smile-production.up.railway.app/process-one/async \
     -H "Content-Type: application/json" \
     -d "{\"video_id\":\"VIDEO_ID_HERE\",\"podcast\":\"9operators\"}"
   ```
   Copy the `job_id` from the response.
3. **Get logs (after a few minutes):**
   ```bash
   curl -sS https://superb-smile-production.up.railway.app/jobs/JOB_ID_HERE
   ```
   Use `logs.stderr` (and `logs.stdout`) for yt-dlp and pipeline errors.
4. **Apply fixes in Cursor** using `AUDIO_SYNC_REFERENCE.md` and the codebase, then **commit + push** and redeploy.

---

## 3. References in this repo

- **`AUDIO_SYNC_REFERENCE.md`** — Where audio/sync logic lives, what to check when yt-dlp or sync misbehaves.
- **`docs/SYNC_AND_DEBUG_IN_CURSOR.md`** (this file) — Keep local = GitHub; use process-one + /jobs for quick logs; debug in Cursor.

When asking the agent to fix something, you can say: *"Use @AUDIO_SYNC_REFERENCE.md and keep local and GitHub in sync per docs/SYNC_AND_DEBUG_IN_CURSOR.md."*
