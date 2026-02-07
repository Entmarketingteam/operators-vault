# Operators Vault – Plan & Status

**Purpose:** Single source for plan, current status, and next steps. Keep this open when handing off.

---

## Goals (Original Plan)

- Ingest episodes from **9 Operators**, **Marketing Operator**, **Finance Operator** (CSVs + YouTube Data API).
- Pipeline: YouTube → audio (yt-dlp) → Deepgram (diarization) → chunk → Anthropic insight extraction → Supabase (videos, transcriptions, segments, insights). Search: Postgres FTS (private; Supabase Auth).
- CLI and HTTP API for: seed, process one, process all, **fetch-new** (YouTube channels), **process-new** (only unprocessed).
- n8n workflows for one-off process and **cron sync** (fetch-new + process-new).
- Searchable vault: `GET /search` over Postgres FTS (Bearer token required).
- **Hosted and working like mfmvault.com:** Custom domain, public search UI at that URL, n8n sync running. See **`HOSTING.md`**.

---

## Status: Done

| Area | What |
|------|------|
| Schema | `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people`; `channel_id`, `published_at` on videos |
| run_schema | Applies `sql/schema.sql`; splits by `;`; .env fallback |
| youtube_client | load_from_csv, load_all_seed_csvs, resolve_channel_id, fetch_channel_videos (published_at), get_channel_handle; DEFAULT_CHANNEL_HANDLES; YOUTUBE_CHANNEL_* override |
| pipeline | --seed-csvs, --seed-csvs --process-all, --process, --fetch-new, --process-new; _ensure_video(channel_id, published_at); _fetch_new, _get_unprocessed |
| api | POST /process, /fetch-new, /process-new, /sync, /sync/async, /process-new/async; GET /jobs/{id}, /health, /search, /search-ui, / |
| Prompts | extract_insights_system, make_framework_content, timestamp_extraction, title_generation (operators) |
| n8n | n8n-workflow.json (process one), n8n-workflow-fetch-new.json (cron → /sync) |
| Scripts | run_schema, run_all (schema + fetch-new + process-new; --seed-csvs, --schema-only), import_n8n_workflow, install_wheels |

---

## Status: Not Done / Optional

- **Optional CSV backfill:** `python pipeline.py --seed-csvs --process-all` if CSVs are in `%USERPROFILE%\Downloads\`.
- **Optional:** Search-ui “Sign in with Google/Email” on the page (Supabase JS) so users don’t copy-paste token.
- **Optional:** Custom domain per `HOSTING.md`; Doppler sync (`doppler login` + `setup`, then `python scripts/sync_google_oauth_to_doppler.py`).

---

## Next Steps (When Picking Up)

1. **Done:** Postgres search migration applied; `SUPABASE_JWT_SECRET` on Railway; Supabase Auth (Email + Google) enabled via `enable_supabase_auth.py`; n8n sync daily; Google OAuth in Supabase.
2. **Optional backfill:** `python pipeline.py --seed-csvs --process-all` (CSVs in `%USERPROFILE%\Downloads\`).
3. **If “keep building”:** Add Supabase JS sign-in on `/search-ui`; more search filters; custom domain.

---

## Handoff

- **New agent / developer:** Read `HANDOFF.md` first, then this file and `PROGRESS.md`.
- **Repo:** https://github.com/Entmarketingteam/operators-vault  
- **Local:** `C:\Users\ethan.atchley\operators-vault`
- **Where we are:** Railway live. Search is Postgres FTS (private; JWT). Finance channel: @FinanceOperatorsFOPS. n8n sync recommended daily.
