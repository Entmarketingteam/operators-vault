# Operators Vault

Podcast intelligence platform for **9 Operators**, **Marketing Operator**, and **Finance Operator**: transcriptions, insight extraction, searchable vault (Supabase Postgres FTS; private search with Supabase Auth).

## Setup

1. **Python 3.10+** and a virtualenv:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Environment:** A `.env` file exists with placeholders. Replace them with your real keys:
   - `DATABASE_URL` — Supabase → [Database → Connect](https://supabase.com/dashboard/project/wbdwnlzbgugewtmvahwg/settings/database) → URI → Direct; replace `[YOUR-PASSWORD]` with your DB password.
   - `DATABASE_URL`, `YOUTUBE_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_JWT_SECRET` (for private search auth), `N8N_HOST`, `N8N_API_KEY`.
   Required for the pipeline: `DATABASE_URL`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`. For `--fetch-new`: `YOUTUBE_API_KEY`. For `/search` (private): `SUPABASE_JWT_SECRET` (Supabase project → Settings → API → JWT secret). YouTube channels: 9 Operators `@Operators9`, Marketing `@MarketingOperators`, Finance `@FinanceOperatorsFOPS`.

3. **Supabase:** Create a project, add `DATABASE_URL` to `.env`, then run:
   ```bash
   python scripts/run_schema.py
   python scripts/run_migrate_postgres_search.py
   ```
   The migration adds FTS indexes and search functions (insights + timestamp moments). Enable **Auth** (Email/Password + Google OAuth) in Supabase Dashboard → Authentication → Providers.

4. **Search (private):** Set `SUPABASE_JWT_SECRET` in `.env` (Supabase → Settings → API → JWT secret). `/search` and search-ui require a Bearer token from Supabase Auth (email or Google sign-in).

## Usage

**Process a single video:**
```bash
python pipeline.py --process VIDEO_ID
```

**Seed from CSVs** (9 Operators, Marketing Operator, Finance Operator):
```bash
python pipeline.py --seed-csvs
```

**Process all videos from seed CSVs:**
```bash
python pipeline.py --seed-csvs --process-all
```

**Store CSV links in Supabase** (then run backfill from DB without re-uploading):
```bash
python pipeline.py --seed-csvs-to-db    # CSVs from %USERPROFILE%\\Downloads\\ -> seed_links
python pipeline.py --seed-from-db --process-all   # seed_links -> videos, then process unprocessed
```
Or from the API: `POST /seed-links/csv` to store; `POST /backfill` (no body) to run from `seed_links`.

**Fetch new videos from YouTube channels** (9 Operators, Marketing, Finance; requires `YOUTUBE_API_KEY`):
```bash
python pipeline.py --fetch-new
python pipeline.py --fetch-new --process-new   # fetch then process unprocessed
```

**Process only videos that have no transcription yet:**
```bash
python pipeline.py --process-new
```

**One-command sync** (schema + fetch-new + process-new):
```bash
python scripts/run_all.py
python scripts/run_all.py --seed-csvs   # include CSV seed before fetch
python scripts/run_all.py --schema-only # only apply schema
```

**Pipeline API (for n8n or automation):**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
- `POST /process` — body `{"video_id": "VIDEO_ID", "podcast": "9operators"}`  
- `POST /fetch-new` — fetch from YouTube channels and upsert into `videos`  
- `POST /process-new` — process all videos with no transcription yet  
- `POST /sync` — run fetch-new then process-new in one call (for cron)  
- `GET /health` — env and connectivity checks (database, youtube, deepgram, anthropic)  
- `GET /search?q=...&podcast=...&category=...&video_id=...&limit=20&type_=insights|moments|all` — **private**; search via Postgres FTS (requires `Authorization: Bearer <supabase_access_token>`)
- `GET /search-ui` — HTML search UI (Discover); paste token to search (insights + moments, jump-to timestamp)
- `GET /episodes-ui` — Episodes catalog (Catalog); filter by podcast (9 Operators, Marketing, Finance, TITANS)
- `GET /insights-ui` — Listen; browse insights by type (Quotes, Frameworks, Business ideas, etc.)
- `GET /people-ui` — People directory
- `GET /ask-ui` — Ask; chat over the vault (search + LLM reply with citations)
- `GET /episodes`, `GET /insights`, `GET /people` — list endpoints (Bearer token); `POST /chat` — chat (Bearer token)
- `GET /config` — public config (`apiBase`, `supabaseUrl`, `supabaseAnonKey`) for frontends
- `POST /sync/async`, `POST /process-new/async` — like `/sync` and `/process-new` but return 202 with `job_id`; poll `GET /jobs/{job_id}` for status
- `POST /seed-links` — JSON `{"links": [{video_id, podcast, title?, duration_seconds?, url?}]}`; upsert into `seed_links` (Supabase).  
- `POST /seed-links/csv` — multipart CSVs (`9operators`, `marketing_operator`, `finance_operators`, `titans`, `operators_and_titans`); upsert into `seed_links`.  
- `POST /backfill` — run backfill from `seed_links`: seed into `videos` then process unprocessed. With optional CSV uploads: merge into `seed_links` first. With no body: use existing `seed_links`. Returns 202 + `job_id`; poll `GET /jobs/{job_id}`.  

**Automatic sync (new videos auto-processed):**  
- **Railway Cron Job** (recommended): Railway → New → Cron Job, schedule `0 */3 * * *` (every 3 hours), command: `curl -X GET "https://your-app.railway.app/trigger-sync"`. See `docs/AUTOMATIC_SYNC.md`.  
- **n8n workflow:** Run `python scripts/setup_n8n_workflows.py` (sets up workflow calling `GET /trigger-sync` every 6 hours). Then activate "Operators Vault – Sync New Episodes" in n8n.  
- **Manual:** `GET /trigger-sync` or `POST /sync/async` (returns 202 + job_id; poll `GET /jobs/{job_id}`).

## Deployment (GitHub → Railway + Vercel)

- **Railway** runs the FastAPI app (`api.py`). Push to the connected branch (e.g. `master`) to trigger a deploy. All UI routes (`/search-ui`, `/episodes-ui`, `/insights-ui`, `/people-ui`, `/ask-ui`) and API endpoints are served from Railway. Set env in Railway → Variables (see `docs/DEPLOYMENT_ENV.md`).
- **Vercel** can host the static front end in `web/` (root directory set to `web`). The nav in `web/index.html` links to the Railway API for Discover, Listen, Catalog, People, Ask, and API docs. Push to the same repo to update both; Vercel redeploys when the repo is connected.
- **GitHub:** Repo is the single source. No secrets in the repo; use Railway and Vercel env (or Doppler for local). After pushing, confirm Railway deploy and, if using Vercel, that the build succeeds.

## Project layout

- `PLAN.md` – Plan, status, next steps (handoff)
- `HANDOFF.md` – Developer/agent handoff; read first in a new session
- `PROGRESS.md` – Done / Not done / How to run
- `sql/schema.sql` – Supabase schema
- `scripts/run_schema.py` – Apply schema (uses `DATABASE_URL` from `.env`)
- `scripts/import_n8n_workflow.py` – Import `n8n-workflow.json` to n8n via API (`N8N_HOST`, `N8N_API_KEY`)
- `scripts/run_migrate_postgres_search.py` – Apply Postgres FTS migration (`sql/migrate_postgres_search.sql`)
- `youtube_client.py` – Fetch from channels or parse CSVs
- `audio_extractor.py` – Download audio (yt-dlp)
- `deepgram_client.py` – Transcribe with diarization
- `insight_extractor.py` – LLM extraction (Anthropic, Operators prompts)
- `pipeline.py` – Orchestrator
- `api.py` – FastAPI: process, fetch-new, sync, backfill, seed-links/csv; GET /search, /search-ui, /episodes-ui, /insights-ui, /people-ui, /ask-ui, /episodes, /insights, /people, POST /chat, GET /config, /health, /jobs
- `n8n-workflow.json` – n8n: one-off process video
- `n8n-workflow-fetch-new.json` – n8n: cron every 6h, `POST /sync`
- `scripts/run_all.py` – one-command: schema, optional --seed-csvs, fetch-new, process-new
- `prompts/operators/` – Insight, title, timestamp, framework prompts
- `meilisearch-setup.md` – Index config
