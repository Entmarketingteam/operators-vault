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
| Schema | `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people`; Phase 1: `view_count`, `like_count`, `thumbnail_url`, etc.; `titans` podcast |
| run_schema | Applies `sql/schema.sql`; run_migrate_phase1 (YouTube stats + TITANS) |
| youtube_client | load_from_csv (incl. operators_and_titans, infer_podcast_from_title), fetch_channel_videos, fetch_playlist_videos (TITANS), DEFAULT_CSV_PATHS |
| pipeline | --seed-csvs, --seed-csvs-to-db, --seed-from-db, --fetch-new (incl. TITANS playlist), --process-new; titans in CLI |
| api | POST /process, /fetch-new, /process-new, /sync, /sync/async, /backfill, /seed-links/csv (incl. operators_and_titans); GET /search, /search-ui, /episodes, /episodes-ui, /people, /config, /health, /stats |
| UI | Search (Discover), Episodes catalog (Catalog) with nav; TITANS in filters; title strip for TITANS display |
| Doppler | docs/DOPPLER.md; run_with_doppler.py; enable_supabase_auth accepts SUPABASE_API_KEY2 |
| Scripts | run_all (--csv-only, --migration-only), run_migrate_phase1, run_with_doppler (migrate, run_all) |

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
