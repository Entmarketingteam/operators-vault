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
| api | POST /process, /fetch-new, /process-new, /sync; GET /health, /search, / |
| Prompts | extract_insights_system, make_framework_content, timestamp_extraction, title_generation (operators) |
| n8n | n8n-workflow.json (process one), n8n-workflow-fetch-new.json (cron → /sync) |
| Scripts | run_schema, run_all (schema + fetch-new + process-new; --seed-csvs, --schema-only), import_n8n_workflow, install_wheels |

---

## Status: Not Done / Blocked

- **Schema apply and pipeline runs** not successfully executed in the original dev environment (Supabase DB host unreachable via DNS; depends on network).
- **Finance Operators** default handle `FinanceOperators` may be wrong; override with `YOUTUBE_CHANNEL_FINANCE_OPERATORS` if needed.

---

## Next Steps (When Picking Up)

1. **Validate run:** On a host with DB + Meilisearch + YouTube API: `python scripts/run_schema.py` then `python scripts/run_all.py`. Fix any env or runtime errors.
2. **Optional backfill:** `python pipeline.py --seed-csvs --process-all` if CSVs are in `%USERPROFILE%\Downloads\` and you want to process the initial lists.
3. **API checks:** Run `uvicorn api:app --host 0.0.0.0 --port 8000`, then `GET /health`, `GET /search?q=...`.
4. **n8n:** Import `n8n-workflow-fetch-new.json`, set URL to `/sync`, activate schedule.
5. **If “keep building”:** Consider: background/async for `POST /process-new` and `POST /sync` (return 202 + job), or a simple UI for /search; or more filters/ordering on /search.

---

## Handoff

- **New agent / developer:** Read `HANDOFF.md` first, then this file and `PROGRESS.md`.
- **Repo:** https://github.com/Entmarketingteam/operators-vault  
- **Local:** `C:\Users\ethan.atchley\operators-vault`
