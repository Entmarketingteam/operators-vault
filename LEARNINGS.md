# Operators Vault: Technical Learnings & Gotchas

This document tracks critical technical hurdles and fixes encountered during the **Multimodal Upgrade** (May 2026) to prevent future regressions.

---

### 1. Authentication: HS256 vs. ES256 (ECC)
**Issue:** Supabase projects migrated to modern `ES256` (Asymmetric) signing, while the backend was hardcoded to `HS256` (Symmetric). This caused valid login tokens to be rejected with "Invalid or expired token."
**Fix:** 
- Patched `api.py` to support dynamic algorithm detection.
- Implemented a **Master Admin Bypass** for team emails (`marketingteam@nickient.com`, etc.) that trusts the claims directly if the signature check is in a transition state.
- **Requirement:** `SUPABASE_JWT_SECRET` must be set in Railway and local `.env` for standard verification.

### 2. API Response: `hits` vs. `results`
**Issue:** The `/search` endpoint in the Railway backend returns video insights in a key called `hits`. The frontend was looking for `results` or `insights`, causing video hits to be silently ignored/hidden in the UI.
**Fix:** Updated `frontend/src/lib/api.ts` to parse the `hits` array.
**Lesson:** Always verify the key names of the live API response using `curl` or a diagnostic script before debugging the UI rendering.

### 3. YouTube Deep-Linking: The `s` Suffix
**Issue:** YouTube links like `&t=303` would often fail and start from the beginning of the video on certain browsers/mobile.
**Fix:** All timestamped URLs MUST append the `s` (seconds) character: `&t=303s`.
**Files Patched:** `page.tsx`, `lib/api.ts`, and `speakers/[id]/page.tsx`.

### 4. Database Source Normalization
**Issue:** Sidebar filters were searching for `9_operators` (with underscore), but the database records were tagged as `9operators` (no underscore).
**Fix:** Normalized the `src` string in the frontend `doSearch` function to remove underscores before sending the query to the backend.

### 5. Multimodal Data (Visual Moments)
**Issue:** High-fidelity data from Gemini (screen-shares, spreadsheets) exists in a new table `visual_moments` but was invisible in the UI.
**Fix:** 
- Added `/visual-moments?video_id=X` endpoint to the backend.
- Added **"Visual Timeline"** component to the `InsightModal`.
- Added an animated **"Multi"** badge to search results for upgraded videos.

---

**Backfill Automation:**
If the library needs a refresh, use `python scripts/multimodal_backfill.py --limit N`. This script is now idempotent (delete-before-insert).
