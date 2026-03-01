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
| Schema | `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people`; Phase 1: `view_count`, `like_count`, `thumbnail_url`, etc.; `titans` podcast; Phase 2: `companies`, `insight_companies`, `video_companies`, `insight_people`, slugs; Phase 3: `visual_moments` |
| Migrations | Phase 1 (YouTube stats + TITANS), Phase 2 (People & Companies), Phase 3 (Visual moments); all integrated into `run_all.py` |
| youtube_client | load_from_csv (incl. operators_and_titans, infer_podcast_from_title), fetch_channel_videos, fetch_playlist_videos (TITANS), DEFAULT_CSV_PATHS |
| pipeline | --seed-csvs, --seed-csvs-to-db, --seed-from-db, --fetch-new (incl. TITANS playlist), --process-new; titans in CLI; Phase 2: people extraction from segments, companies extraction from insights/videos; Phase 3: visual moments extraction |
| Extraction | `people_extractor.py` (speaker_label → people, link insights), `company_extractor.py` (LLM extraction), `visual_extractor.py` (screen-share/slide detection) |
| api | POST /process, /fetch-new, /process-new, /sync, /sync/async, /backfill, /seed-links/csv; GET /search (person_id, company_id, is_panzerism filters), /search-ui, /episodes, /episodes-ui, /people, /people-ui, /insights, /insights-ui, /chat, /ask-ui, /person/{slug}, /person-ui/{slug}, /company/{slug}, /company-ui/{slug}, /visuals, /related, /config, /health, /stats |
| UI | Search (Discover) with copy link, person/company filters, Panzerisms checkbox; Episodes catalog (Catalog); People directory (links to person-ui); Insights by type (Listen) with Panzerisms filter; Ask/Chat; Person detail pages; Company detail pages |
| Doppler | docs/DOPPLER.md; run_with_doppler.py; enable_supabase_auth accepts SUPABASE_API_KEY2 |
| Scripts | run_all (--csv-only, --migration-only, runs all 3 migrations), run_migrate_phase1, run_migrate_phase2, run_migrate_phase3, run_with_doppler |

---

## Status: Not Done / Optional

- **Optional CSV backfill:** `python pipeline.py --seed-csvs --process-all` if CSVs are in `%USERPROFILE%\Downloads\`.
- **Optional:** Search-ui “Sign in with Google/Email” on the page (Supabase JS) so users don’t copy-paste token.
- **Optional:** Custom domain per `HOSTING.md`; Doppler sync (`doppler login` + `setup`, then `python scripts/sync_google_oauth_to_doppler.py`).

---

## Next Steps (When Picking Up)

### ⚡ IMMEDIATE — Run locally (not on Railway)

Railway's cloud IP is blocked by YouTube — audio downloads and caption API both fail.
**40 new videos were fetched on 2026-03-01 and are sitting unprocessed in the DB.**
Run processing on a non-cloud machine (home PC, Mac, etc.):

```bash
git clone https://github.com/Entmarketingteam/operators-vault
cd operators-vault
pip install -r requirements.txt
# Copy .env from the other machine or pull from Doppler (see docs/DOPPLER.md)
python pipeline.py --process-new
```

This will process all ~53 unprocessed videos. Takes a few hours. Watch for errors in stdout.

### Current data state (as of 2026-03-01)

| Podcast | Videos in DB | Processed |
|---------|-------------|-----------|
| 9 Operators | ~33 | 14 |
| Marketing Operator | ~30 | 8 |
| Finance Operators | ~13 | 1 |

### After processing runs

1. **Custom domain** — Add to Railway → Settings → Public Networking. See `HOSTING.md`.
2. **Auth wall decision** — `/search` requires Supabase Bearer token. If public-facing, consider removing auth or adding public read-only mode.
3. **TITANS playlist** — `YOUTUBE_PLAYLIST_TITANS` not set in Railway env; TITANS episodes are not being synced. Add the playlist ID to unlock that podcast.

### If Railway processing is needed long-term

Set `YT_DLP_PROXY` in Railway env vars to a residential proxy URL (Bright Data, Oxylabs, Smartproxy). Same var covers both yt-dlp and caption fallback.

---

## Handoff

- **New agent / developer:** Read `HANDOFF.md` first, then this file and `PROGRESS.md`.
- **Repo:** https://github.com/Entmarketingteam/operators-vault  
- **Local:** `C:\Users\ethan.atchley\operators-vault`
- **Where we are:** Railway live. Search is Postgres FTS (private; JWT). Finance channel: @FinanceOperatorsFOPS. n8n sync recommended daily.
