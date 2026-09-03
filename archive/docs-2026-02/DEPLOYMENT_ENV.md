> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Deployment env – Railway & Vercel (editable on your end)

All credentials and URLs are **editable only in your dashboards** (Railway → Variables, Vercel → Environment Variables). This repo has no secrets; it only reads from env. Use the tables below to set everything in one place.

---

## Railway (API / backend)

Set these in **Railway → your service → Variables**. These are the only place the API gets DB, Supabase, and API keys.

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | Supabase Postgres connection string (Dashboard → Connect → Connection string → URI). Use **Direct** or **Session pooler** if Direct is unreachable. |
| `SUPABASE_URL` | Yes | Supabase project URL, e.g. `https://xxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Yes (for /config & UI) | Supabase anon/public key (Dashboard → Settings → API → anon public). Used by search UI and `GET /config`. |
| `SUPABASE_JWT_SECRET` | Yes (for /search) | JWT secret (Dashboard → Settings → API → JWT Secret). Used to verify Bearer tokens for `GET /search`. |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Service role key; can be used as fallback for JWT verification. Prefer `SUPABASE_JWT_SECRET` for /search. |
| `PUBLIC_API_BASE` | Optional | Public URL of this API (e.g. `https://superb-smile-production.up.railway.app`). If **empty**, search UI served from same host uses same-origin. Set this when the frontend is on **Vercel** so it knows the API URL; also returned by `GET /config`. |
| `YOUTUBE_API_KEY` | For fetch-new | YouTube Data API key for `POST /fetch-new` and pipeline. |
| `YOUTUBE_PLAYLIST_TITANS` | Optional | TITANS playlist ID so fetch-new pulls TITANS episodes. |
| `DEEPGRAM_API_KEY` | For processing | Transcription (pipeline / process-new). |
| `ANTHROPIC_API_KEY` | For processing | Insight extraction (pipeline / process-new). |
| `CORS_ORIGINS` | Optional | Comma-separated origins for `/search` (e.g. your Vercel URL). Default `*` allows any. |
| `SYNC_TRIGGER_KEY` | Optional | If set, GET `/trigger-sync` and `/trigger-process-new` require `?key=<value>`. Use for cron/n8n so only you can trigger sync. |

**Sync / process (use async or GET trigger to avoid 502 on Railway):**
- **POST /sync/async** – Start full sync (fetch-new + process-new) in background; returns 202 + `job_id`. Poll **GET /jobs/{job_id}** for status.
- **POST /process-new/async** – Start processing all unprocessed videos; returns 202 + `job_id`.
- **GET /trigger-sync** – Same as POST /sync/async but GET (for cron/n8n). Optional: `?key=SYNC_TRIGGER_KEY`.
- **GET /trigger-process-new** – Same as POST /process-new/async but GET. Optional: `?key=SYNC_TRIGGER_KEY`.

**Quick checks:**  
- `GET /health` – reports database, youtube, deepgram, anthropic.  
- `GET /config` – returns `{ apiBase, supabaseUrl, supabaseAnonKey }` from the vars above (so any frontend can read config from the API).

---

## Vercel (frontend only)

Use this **only if** you deploy a separate frontend (e.g. Next.js or static site) on Vercel that calls the Railway API.

| Variable | Required | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_VAULT_API_BASE` or `VITE_VAULT_API_BASE` | If app needs API URL | Railway API URL (e.g. `https://superb-smile-production.up.railway.app`). Or have the app call `GET <api>/config` once and use `apiBase` from the response. |
| `NEXT_PUBLIC_SUPABASE_URL` / `VITE_SUPABASE_URL` | If app does Supabase Auth | Same as Railway `SUPABASE_URL`. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `VITE_SUPABASE_ANON_KEY` | If app does Supabase Auth | Same as Railway `SUPABASE_ANON_KEY`. |

**If the “frontend” is only the search UI served by Railway** (e.g. `https://your-railway.app/search-ui`): you don’t need any Vercel env for the vault; set everything in **Railway** and leave `PUBLIC_API_BASE` empty so the UI uses same-origin.

---

## Single source of truth

- **Backend (search, sync, backfill, health):** Railway env only.  
- **Public config for any frontend:** `GET https://<railway-url>/config` returns `apiBase`, `supabaseUrl`, `supabaseAnonKey` from Railway env. Your Vercel app can fetch that once and use it so you only edit **Railway** for API + Supabase URLs/keys.  
- **Local (this machine):** Use **Doppler** so scripts get the same values as Railway. Run `doppler setup` in the repo, add the same variable names in Doppler, then run e.g. `doppler run -- python scripts/run_all.py --csv-only`. See **docs/DOPPLER.md**.

---

## Where each value comes from (Supabase)

| What you need | Where in Supabase |
|---------------|-------------------|
| `SUPABASE_URL` | Dashboard → Project URL |
| `SUPABASE_ANON_KEY` | Settings → API → Project API keys → **anon** **public** |
| `SUPABASE_JWT_SECRET` | Settings → API → JWT Settings → **JWT Secret** |
| `SUPABASE_SERVICE_ROLE_KEY` | Settings → API → **service_role** (secret) |
| `DATABASE_URL` | Connect → Connection string → **URI** (replace password) |

Once these are set in **Railway → Variables**, the API and `GET /config` use them; you can change them anytime in Railway (or Vercel for frontend-only vars) without touching the repo.

---

## Pushing to GitHub (Railway + Vercel)

- **Same repo** drives both deployments. Push to the branch connected to Railway (e.g. `master`) to deploy the API and all server-rendered UIs: `/search-ui`, `/episodes-ui`, `/insights-ui`, `/people-ui`, `/ask-ui`, plus `GET /episodes`, `/insights`, `/people`, `POST /chat`, etc.
- If **Vercel** is connected to this repo with root directory `web/`, each push also redeploys the static site; nav there links to the Railway URLs above.
- **No secrets in the repo.** All credentials live in Railway Variables, Vercel Environment Variables, or (locally) Doppler.
