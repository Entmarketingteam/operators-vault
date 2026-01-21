# Operators Vault – Plan & Status

**Purpose:** Single source for plan, current status, and next steps. Keep this open when handing off.

---

## Goals (Original Plan)

- Ingest episodes from **9 Operators**, **Marketing Operator**, **Finance Operator** (CSVs + YouTube Data API).
- Pipeline: YouTube → audio (yt-dlp) → Deepgram (diarization) → chunk → Anthropic insight extraction → Supabase (videos, transcriptions, segments, insights) + Meilisearch (operators_insights).
- CLI and HTTP API for: seed, process one, process all, **fetch-new** (YouTube channels), **process-new** (only unprocessed).
- n8n workflows for one-off process and **cron sync** (fetch-new + process-new).
- Searchable vault: `GET /search` over Meilisearch.

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

## Status: Not Done / To Fix

- **`GET /search`** returns `invalid_api_key` from Meilisearch. Set `MEILISEARCH_API_KEY` in Railway to a key with **search** (and index) on `operators_insights`; get from Meilisearch project.
- **Finance Operators** default handle `FinanceOperators` may be wrong; override with `YOUTUBE_CHANNEL_FINANCE_OPERATORS` if needed.
- **Optional CSV backfill:** `python pipeline.py --seed-csvs --process-all` if CSVs are in `%USERPROFILE%\Downloads\` (run where DB reachable).

---

## Next Steps (When Picking Up)

1. **Meilisearch:** Fix `MEILISEARCH_API_KEY` on Railway (key with search on `operators_insights`). See `meilisearch-setup.md` § "Fix `/search` on Railway". Then `GET /search?q=...` and `/search-ui` work.
2. **Optional backfill:** `python pipeline.py --seed-csvs --process-all` (CSVs in `%USERPROFILE%\Downloads\`).
3. **If “keep building”:** (done) `POST /sync/async`, `POST /process-new/async` (202 + job), `GET /jobs/{job_id}`; `GET /search-ui`; `?sort=` on `/search`. Further: more filters, or wire n8n to `/sync/async`.

---

## Handoff

- **New agent / developer:** Read `HANDOFF.md` first, then this file and `PROGRESS.md`.
- **Repo:** https://github.com/Entmarketingteam/operators-vault  
- **Local:** `C:\Users\ethan.atchley\operators-vault`
- **Where we are:** Railway https://superb-smile-production.up.railway.app live. `DATABASE_URL` = Supabase Session pooler (aws-0-us-west-2). `/health` ok; `POST /sync` works. n8n **Operators Vault – Sync New Episodes** updated (Schedule Trigger `rule.interval`), **Active** every 6h. `n8n-workflow-fetch-new.json` and `setup_n8n_workflows.py` idempotent. **`GET /search`** → `invalid_api_key`: fix `MEILISEARCH_API_KEY` on Railway.
