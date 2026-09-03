> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Operators Vault – Developer / Agent Handoff

**Read this first when picking up in a new session.** Repo: https://github.com/Entmarketingteam/operators-vault

---

## Resume in New Chat

When you come back in a new chat, you can resume with:

> Read HANDOFF.md and PLAN.md in operators-vault and continue from the Next steps there.

Or:

> Open C:\Users\ethan.atchley\operators-vault, read HANDOFF.md then PLAN.md, and pick up from the Next steps.

---

## 1. What This Project Is

Podcast intelligence for **9 Operators**, **Marketing Operator**, **Finance Operator**: YouTube → audio → Deepgram transcription → LLM insight extraction (Anthropic) → Supabase. Search is Postgres FTS (private; Supabase Auth). CSVs or `--fetch-new` (YouTube API) seed videos; `--process-new` runs the pipeline on unprocessed videos.

---

## 2. Where We Are (Current State)

- **Implemented and committed:** Schema, Phase 1 migration (YouTube stats + TITANS), Postgres FTS, pipeline (seed/fetch/process, titans, operators_and_titans CSV), API: search, **episodes**, **insights**, **people**, **POST /chat**, seed-links/csv, backfill; UIs: **/search-ui**, **/episodes-ui**, **/insights-ui**, **/people-ui**, **/ask-ui**; Doppler docs and run_with_doppler; web/ front end with nav to Railway UIs.
- **Railway:** https://superb-smile-production.up.railway.app — API + all UIs. Set `SUPABASE_JWT_SECRET`, `DATABASE_URL`, etc. (see `docs/DEPLOYMENT_ENV.md`). n8n **Operators Vault – Sync New Episodes** recommended **daily**.
- **Vercel:** Static `web/` (root dir `web`); nav links to Railway for Discover, Listen, Catalog, People, Ask. Push to GitHub deploys both Railway and Vercel when repo is connected.
- **Hosting:** See **`HOSTING.md`** for custom domain. Search is Postgres; no Meilisearch.

---

## 3. Repo and Local Paths

- **Git:** https://github.com/Entmarketingteam/operators-vault (origin over HTTPS). Branch: `master`.
- **Local project root:** `C:\Users\ethan.atchley\operators-vault`
- **Key files:**
  - `PLAN.md` – Plan + status + next steps (keep this open as the “plan”)
  - `PROGRESS.md` – Done / Not done / How to run / Env / CSV paths
  - `README.md` – Setup and usage
  - `HANDOFF.md` – This file
  - `HOSTING.md` – Custom domain + “hosted like mfmvault.com” checklist
  - `api.py` – FastAPI app
  - `pipeline.py` – CLI: --seed-csvs, --seed-csvs-to-db, --seed-from-db, --process, --fetch-new, --process-new
  - `youtube_client.py` – CSVs + resolve_channel_id, fetch_channel_videos
  - `sql/schema.sql` – base schema; `sql/migrate_postgres_search.sql` – FTS + search functions
  - `scripts/run_schema.py` – Apply schema; `scripts/run_migrate_postgres_search.py` – apply search migration
  - `scripts/run_all.py` – schema + fetch-new + process-new (optional --seed-csvs)

---

## 4. Environment and Secrets

- **`.env`** in project root (gitignored). Contains: `DATABASE_URL`, `YOUTUBE_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_JWT_SECRET` (for private search), `N8N_HOST`, `N8N_API_KEY`, etc.
- **Deps:** `pip install -r requirements.txt`. If pip hits HTTP/2 errors: `.\scripts\install_wheels.ps1` then `pip install -r requirements.txt`. `yt-dlp` must be on PATH or from the yt-dlp Python package.

---

## 5. Commands to Run (Once DB and Network Work)

```powershell
cd C:\Users\ethan.atchley\operators-vault
# Deps (if needed)
.\scripts\install_wheels.ps1
pip install -r requirements.txt

# Schema + Postgres search migration
python scripts/run_schema.py
python scripts/run_migrate_postgres_search.py

# One-command sync (fetch from YouTube + process new)
python scripts/run_all.py

# Or with CSV seed first
python scripts/run_all.py --seed-csvs

# API
python -m uvicorn api:app --host 0.0.0.0 --port 8000
# Then: GET /health, POST /sync, POST /process. GET /search requires Authorization: Bearer <supabase_access_token>.
```

---

## 6. Instructions for a New Agent (Cursor / Full-Context Window)

1. **Open:** `C:\Users\ethan.atchley\operators-vault` and read, in order: `HANDOFF.md`, `PLAN.md`, `PROGRESS.md`.
2. **Context:** The pipeline is built. Run `run_schema`, then `run_migrate_postgres_search`, then `run_all` or `--seed-csvs --process-all`. Search is private (Supabase JWT). `YOUTUBE_API_KEY` is set in `.env`.
3. **If the user says “keep building”:** Validate schema + migration, run_all, /health, /search (with Bearer token) (`YOUTUBE_CHANNEL_FINANCE_OPERATORS`), (c) extending API or pipeline per `PLAN.md` “Next steps”.
4. **If the user reports errors:** Use `GET /health` and `scripts/run_schema.py` / `pipeline.py --fetch-new` for diagnosis. Check `.env` and that `yt-dlp` is available for `audio_extractor`.

---

## 7. CSV Paths (for --seed-csvs)

| Podcast            | Default path                                                                 |
|--------------------|------------------------------------------------------------------------------|
| 9operators         | `%USERPROFILE%\Downloads\Operators Podcast Video Youtube Links.csv`          |
| marketing_operator | `%USERPROFILE%\Downloads\Marketing Operators Podcast Video Youtube Links.csv`|
| finance_operators  | `%USERPROFILE%\Downloads\Finance Operators Podcast Video Youtube Links.csv`  |

---

## 8. n8n

- `n8n-workflow.json` – One-off: Manual/Webhook → Set (video_id, podcast) → `POST /process`.
- `n8n-workflow-fetch-new.json` – Cron (recommended **daily**) → `POST /sync`.
- **`scripts/setup_n8n_workflows.py`** – Imports or updates both workflows with `RAILWAY_APP_URL`; idempotent. Requires `N8N_HOST`, `N8N_API_KEY`. Run: `python scripts/setup_n8n_workflows.py`. **Operators Vault – Sync New Episodes** uses `rule.interval` (Schedule Trigger 1.2) so API activate works; Process is manual-only.

---

## 9. Railway

- **App:** https://superb-smile-production.up.railway.app  
- **DB:** `DATABASE_URL` = Supabase **Session pooler**.  
- **Search:** Postgres FTS (no Meilisearch). `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set; Meilisearch vars have been removed.
- **One-time:** Add `SUPABASE_JWT_SECRET` so `/search` and search-ui accept Bearer tokens: copy from Supabase → Settings → API → JWT secret into `.env`, then run `python scripts/set_railway_supabase_auth.py` (or set the variable in Railway dashboard).

**Remaining manual step (Auth):** Enable sign-in so `/search-ui` works.
- **Option A (quick):** In [Supabase → Auth → Providers](https://supabase.com/dashboard/project/wbdwnlzbgugewtmvahwg/auth/providers), enable **Email**. For Google: enable **Google** and add OAuth client ID/secret; redirect URI `https://wbdwnlzbgugewtmvahwg.supabase.co/auth/v1/callback`.
- **Option B (script):** Add a [Personal Access Token](https://supabase.com/dashboard/account/tokens) to `.env` as `SUPABASE_MANAGEMENT_TOKEN`. `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are already in `.env`. Run `python scripts/enable_supabase_auth.py` to push them into Supabase and enable Email + Google sign-in.

---

## 10. Doppler

- **Sync Google OAuth to Doppler:** After `doppler login` and `doppler setup` in the repo root, run `python scripts/sync_google_oauth_to_doppler.py` to push `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from `.env` into your Doppler config.
