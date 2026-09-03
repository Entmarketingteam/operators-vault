> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# APIs and env – what you already have vs what’s new

**Context:** The app is already running on Railway (API) and Vercel (front-end). This doc clarifies what’s already wired, where the database lives, and what (if anything) you need to add only for the *extended* plan (chat, embeddings, TITANS, etc.).

---

## 1. What’s already in place (no new keys needed for current live app)

These are already referenced in the code and in `.env.example`. If the app is live on Railway, these are almost certainly set in Railway → Variables:

| Env var | Used by | Purpose |
|--------|---------|--------|
| `DATABASE_URL` | api.py, pipeline.py, scripts | Supabase Postgres connection (single source of truth for vault data). |
| `SUPABASE_URL` | .env.example, scripts | Supabase project URL (e.g. `https://wbdwnlzbgugewtmvahwg.supabase.co`). |
| `SUPABASE_SERVICE_ROLE_KEY` | api.py (JWT fallback), scripts | Server-side Supabase access. |
| `SUPABASE_JWT_SECRET` | api.py | Verifies Bearer tokens for `GET /search`. |
| `YOUTUBE_API_KEY` | youtube_client.py, pipeline, api | Fetch channel/playlist and video metadata. |
| `DEEPGRAM_API_KEY` | deepgram_client.py | Transcribe audio (diarization). |
| `ANTHROPIC_API_KEY` | insight_extractor.py | Extract insights from transcript chunks. |
| `CORS_ORIGINS` | api.py | Optional; comma-separated origins for /search (e.g. your Vercel URL). |

**Search:** The app uses **Postgres full-text search** (FTS), not Meilisearch. So you do **not** need `MEILISEARCH_HOST` or `MEILISEARCH_API_KEY` for the current live app. (Older docs like `HOSTING.md` still mention Meilisearch; that’s legacy.)

**Database:** The “database for everything” is **Supabase Postgres** for the project in your `.env.example` (Supabase URL `wbdwnlzbgugewtmvahwg`). Tables come from `sql/schema.sql`; search uses `sql/migrate_postgres_search.sql`. If `GET /health` and `GET /stats` work on Railway, the DB is in place and reachable.

---

## 2. Where things run

- **Railway:** FastAPI app (API, `/search`, `/sync`, `/search-ui` template, etc.). Env vars above live in Railway → your service → Variables.
- **Vercel:** Front-end (e.g. the web search UI that calls the Railway API). It may use `VaultConfig.apiBase` pointing at your Railway URL and Supabase for auth; those can be in Vercel env or hardcoded in the built app.
- **Supabase:** Postgres database + Auth (and optionally Storage later). No extra “database setup” elsewhere.

---

## 3. n8n – no new API keys; fix URL and workflow

n8n is used to call your API on a schedule (e.g. `POST /sync` or `POST /sync/async`). The app does **not** need an n8n API key to run; n8n needs to know your app’s URL and (optionally) a shared secret if you protect `/sync`.

- **Already in .env.example:** `N8N_HOST`, `N8N_API_KEY` – those are for *pushing* workflows into n8n from scripts (e.g. `scripts/setup_n8n_workflows.py`), not for the app itself.
- **What to check:**
  1. In n8n, open the workflow that should run sync (e.g. “Operators Vault – Sync New Episodes”).
  2. In the HTTP Request node that calls the API, set the URL to your **Railway** URL, e.g. `https://superb-smile-production.up.railway.app/sync` (or your custom domain if you have one).
  3. Method: POST. No body required. If you later add a `SYNC_SECRET`, you can send it in a header and the API can require it.
  4. Set the schedule (e.g. every 6–12 hours) and activate the workflow.

So “n8n not set up correctly” is usually: wrong URL, workflow inactive, or schedule not set – **not** missing API keys for the vault app.

---

## 4. What you only add for the *extended* plan (later phases)

These are **not** required for the app that’s already live. Add them when we implement the corresponding features:

| Env var | When to add | Purpose |
|---------|-------------|--------|
| `OPENAI_API_KEY` | When we add chat + embeddings (Phase 5) | Chat model and embeddings (you chose OpenAI as primary). |
| TITANS playlist/channel | When we add TITANS (Phase 1) | Either same YouTube key with a playlist ID or channel handle in config; no new key. |
| Supabase Storage bucket | When we add visual moments (Phase 3) | Same Supabase project; create a bucket (e.g. `vault-frames`). No new key; use existing `SUPABASE_SERVICE_ROLE_KEY`. |

Optional for auth UX (already partially done per PLAN.md):

- Google OAuth: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in Supabase Auth (or in scripts that configure Supabase). Not required in Railway env for the API.

---

## 5. Quick verification checklist

- [ ] **Railway:** `https://<your-railway-url>/health` returns `"status": "ok"` and checks for database, youtube, deepgram, anthropic.
- [ ] **Railway:** `https://<your-railway-url>/stats` returns per-podcast counts (by_podcast).
- [ ] **Railway:** `https://<your-railway-url>/search-ui` loads; search works with a Supabase JWT (or token paste).
- [ ] **Vercel:** Front-end loads and can call the Railway API (same origin or CORS_ORIGINS).
- [ ] **n8n:** Workflow calls `POST <railway-url>/sync` on a schedule and is Active.
- [ ] **Supabase:** Dashboard → Table Editor shows `videos`, `transcriptions`, `segments`, `insights`, `seed_links` (and FTS migration applied if search works).

You do **not** need to hand off any new secret keys to implement the current live behavior or Phase 1 (TITANS + YouTube stats). The only new key we’ll need when we add chat and embeddings is `OPENAI_API_KEY`, and we can add that to Railway when we reach that phase.

---

## 6. Have we gathered anything from YouTube?

YouTube data only gets into the vault when something **explicitly runs** one of these flows. If neither has been run (or they failed), the `videos` table can be empty and search will have nothing to show.

### How to check

- Call **GET /stats** on your Railway API (e.g. `https://superb-smile-production.up.railway.app/stats`).
- If the response is **`{"by_podcast": {}}`** or each podcast shows **0 videos**, then **nothing has been gathered from YouTube yet** (or ingestion failed).

### How YouTube data gets in (two ways)

1. **Fetch from YouTube channels (recommended first step)**  
   - The app uses the **YouTube Data API** to discover videos by channel:
     - **9 Operators** → channel handle `Operators9`
     - **Marketing Operators** → `MarketingOperators`
     - **Finance Operators** → `FinanceOperatorsFOPS`
   - When you run **fetch-new**, it:
     - Resolves each handle to a channel ID (requires `YOUTUBE_API_KEY`)
     - Fetches up to 50 recent videos per channel
     - Inserts them into the `videos` table (skips videos shorter than 5 minutes)
   - **Ways to run it:**
     - **API:** `POST /fetch-new` (then separately `POST /process-new` or `POST /sync` to transcribe and extract insights).
     - **CLI (local):** `python pipeline.py --fetch-new` (with `DATABASE_URL` and `YOUTUBE_API_KEY` in `.env`).
   - If this has never been run, or `YOUTUBE_API_KEY` was missing/invalid on Railway, or the channel handles are wrong, **no rows will be in `videos`**.

2. **Seed links + backfill**  
   - You can instead (or in addition) populate **`seed_links`** with video IDs (e.g. from CSVs or `POST /seed-links`), then run **backfill**. Backfill copies `seed_links` into `videos` and then processes unprocessed videos. If you never uploaded CSVs or called seed-links, `seed_links` can be empty and backfill would add 0 videos.

### First-time ingestion (recommended)

1. **Confirm env on Railway:** `YOUTUBE_API_KEY` and `DATABASE_URL` are set.
2. **Pull from YouTube into `videos`:** Either **POST** your Railway URL **/fetch-new** (e.g. with curl or from the API docs), or locally run `python pipeline.py --fetch-new` (with `.env` pointing at the same `DATABASE_URL`).
3. **Check again:** **GET /stats** should now show non-zero `videos` per podcast (e.g. `9operators`, `marketing_operator`, `finance_operators`).
4. **Transcribe and index:** Call **POST /process-new** or **POST /sync** (or locally `python pipeline.py --process-new`) so each video gets transcription and insights. After that, search will return results.

So: **if you're not sure we've gathered anything from YouTube, call GET /stats. If by_podcast is empty or all zeros, run fetch-new (and then process-new or sync) once to populate the vault.**
