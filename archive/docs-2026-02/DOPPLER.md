> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Using Doppler for credentials (local & scripts)

You’ve already run `doppler login`. Use Doppler as the single source for API keys and Supabase credentials when running scripts and migrations on this machine.

---

## 1. Link this repo to a Doppler config

In the **operators-vault** directory:

```powershell
cd c:\Users\ethan.atchley\operators-vault
doppler setup
```

- Choose (or create) a **project** (e.g. `operators-vault`).
- Choose an **config** (e.g. `dev` or `prd`).

Doppler will write `.doppler.yaml` in the repo so all later `doppler run` commands use that project/config.

---

## 2. Secrets to have in Doppler

Add these in **Doppler Dashboard → your project → config → Secrets**. Names must match exactly (the app reads `os.environ.get("VAR_NAME")`).

| Secret | Required for | Where to get it |
|--------|----------------|------------------|
| `DATABASE_URL` | Schema, migrations, pipeline, API | Supabase → Connect → Connection string → URI (replace password) |
| `SUPABASE_URL` | API, /config, UI | Supabase → Project URL |
| `SUPABASE_ANON_KEY` | /config, search UI auth | Supabase → Settings → API → anon **public** |
| `SUPABASE_JWT_SECRET` | GET /search (verify tokens) | Supabase → Settings → API → JWT Secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional (JWT fallback, scripts) | Supabase → Settings → API → service_role |
| `SUPABASE_MANAGEMENT_TOKEN` or `SUPABASE_API_KEY2` | Optional (enable_supabase_auth.py) | [Supabase Personal Access Token](https://supabase.com/dashboard/account/tokens) (e.g. `sbp_...`). Storing in Doppler as `supabase_api_key2` works; script accepts both names. |
| `YOUTUBE_API_KEY` | fetch-new, pipeline | Google Cloud Console → YouTube Data API |
| `DEEPGRAM_API_KEY` | process-new (transcription) | Deepgram dashboard |
| `ANTHROPIC_API_KEY` | process-new (insight extraction) | Anthropic console |
| `YOUTUBE_PLAYLIST_TITANS` | Optional (TITANS fetch) | YouTube TITANS playlist ID |
| `PUBLIC_API_BASE` | Optional (if UI on different host) | e.g. `https://superb-smile-production.up.railway.app` |
| `CORS_ORIGINS` | Optional | e.g. your Vercel URL(s), or `*` |
| `RAILWAY_API_TOKEN` | Optional (set_railway_* scripts, create_railway_cron_service.py) | Railway → Account → Tokens |
| `N8N_HOST`, `N8N_API_KEY` | Optional (n8n workflows) | n8n cloud |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional (Supabase Google Auth) | Google Cloud OAuth; used with `enable_supabase_auth.py` and the management token above. |

You can **import** from an existing `.env`: in Doppler Dashboard use **Import** and paste or upload. Or set each secret manually.

---

## 3. Run commands with secrets injected

Any command that needs credentials should be run **under Doppler** so it gets env from your Doppler config:

```powershell
cd c:\Users\ethan.atchley\operators-vault

# Phase 1 migration
doppler run -- python scripts/run_migrate_phase1.py

# Seed from CSV + process (no YouTube API needed if you only use CSV)
doppler run -- python scripts/run_all.py --csv-only

# Full sync (schema + migration + fetch from YouTube + process)
doppler run -- python scripts/run_all.py --seed-csvs

# Only fetch new from YouTube
doppler run -- python pipeline.py --fetch-new

# Only process unprocessed videos
doppler run -- python pipeline.py --process-new
```

Doppler injects the secrets into the environment for that single process; the scripts and API never read from `.env` when you use `doppler run`.

---

## 4. Optional: run script (no need to type `doppler run`)

You can add a small wrapper so you don’t have to type `doppler run --` every time. For example:

```powershell
doppler run -- python scripts/run_all.py --csv-only
```

Or use the provided wrapper:

```powershell
python scripts/run_with_doppler.py run_all --csv-only
python scripts/run_with_doppler.py migrate
```

---

## 5. Sync from .env into Doppler (one-time)

If your secrets are already in a local `.env`:

1. In the repo: `doppler setup` (as above).
2. Either:
   - **Manual:** In Doppler Dashboard, create the secrets listed in the table above and paste values from `.env`.
   - **Script (Google only):** `python scripts/sync_google_oauth_to_doppler.py` pushes only `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from `.env` to Doppler.

There is no script in this repo that pushes **all** `.env` keys to Doppler (to avoid leaking secrets). Add the rest in the Doppler Dashboard or via `doppler secrets set KEY=value` if you prefer CLI.

---

## Summary

- **Doppler** = source of truth for local runs. You edit secrets in Doppler (or Dashboard); scripts stay the same.
- **Railway / Vercel** = source of truth for deployed app. Set the same variable names there (see `docs/DEPLOYMENT_ENV.md`).
- Always run migrations and pipeline with:  
  `doppler run -- python scripts/run_all.py ...`  
  (or the wrapper) so the process gets your Supabase and API keys from Doppler.
