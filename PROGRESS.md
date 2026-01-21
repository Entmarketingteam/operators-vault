# Operators Vault – Progress Checkpoint

**For new agent / developer:** Read **HANDOFF.md** first, then **PLAN.md**. This file is the detailed “Done / Not done / How to run.”

---

## Done

- **Schema** (`sql/schema.sql`): `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people`, `seed_links` (canonical links from CSVs/API); `channel_id`, `published_at` on `videos`.
- **run_schema.py**: Applies schema; loads `.env` via `python-dotenv` or manual fallback.
- **youtube_client.py**: `load_from_csv`, `load_all_seed_csvs`, `resolve_channel_id`, `fetch_channel_videos` (returns `published_at`), `get_channel_handle`; `DEFAULT_CHANNEL_HANDLES` (9operators→Operators9, marketing_operator→MarketingOperators, finance_operators→FinanceOperators). Override via `YOUTUBE_CHANNEL_<PODCAST>`. CSV paths in `USERPROFILE\Downloads`.
- **pipeline.py**: `--seed-csvs`, `--seed-csvs --process-all`, `--seed-csvs-to-db` (CSVs→seed_links), `--seed-from-db`, `--seed-from-db --process-all`, `--process`, `--fetch-new`, `--process-new`; `.env` fallback. `_ensure_video` supports `channel_id`, `published_at`.
- **api.py**: FastAPI `POST /process`, `POST /fetch-new`, `POST /process-new`, `POST /sync`, `POST /sync/async` (202), `POST /process-new/async` (202), `POST /seed-links`, `POST /seed-links/csv`, `POST /backfill` (optional CSVs or from DB; 202), `GET /jobs/{job_id}`, `GET /health`, `GET /search` (`?sort=`), `GET /search-ui`, `GET /`; `.env` fallback.
- **Prompts**: `extract_insights_system`, `make_framework_content`, `timestamp_extraction`, `title_generation` under `prompts/operators/`.
- **n8n**: `n8n-workflow.json`, `n8n-workflow-fetch-new.json` (cron → `/sync`; Schedule Trigger uses `rule.interval` for 1.2); `scripts/setup_n8n_workflows.py` (idempotent, activates Sync); `scripts/import_n8n_workflow.py`.
- **scripts/run_all.py**: One-command: schema, optional `--seed-csvs`, fetch-new, process-new; `--schema-only`.
- **scripts/set_railway_meilisearch.py**: Sets `MEILISEARCH_API_KEY` and `MEILISEARCH_HOST` on Railway from `.env` via Railway GraphQL API; requires `RAILWAY_API_TOKEN` and `~/.railway/config.json` (or `RAILWAY_*_ID` env).
- **Deps workaround**: `scripts/install_wheels.ps1` downloads wheels from PyPI via `Invoke-WebRequest` and runs `pip install --no-deps` (avoids pip HTTP/2 errors). `wheels/` holds cached wheels. Includes: `click`, `annotated_doc`, `pydantic_core`, `typing_inspection`, `annotated_types`, `requests`, `urllib3`, `camel-converter` (FastAPI/uvicorn/meilisearch deps).
- **psycopg2-binary**: Installed from a manually downloaded wheel (pip had HTTP/2 issues with PyPI). Other deps can be installed via `install_wheels.ps1` or `pip install -r requirements.txt` when the network allows.

---

## Not done / To fix

- **`GET /search`**: Was `invalid_api_key`; `MEILISEARCH_API_KEY` and `MEILISEARCH_HOST` have been set on Railway via `python scripts/set_railway_meilisearch.py` (GraphQL API). After Railway redeploys, `/search` and `/search-ui` should work.
- **Optional CSV backfill**: Store links in Supabase first: `POST /seed-links/csv` or `pipeline.py --seed-csvs-to-db`. Then **`POST /backfill`** (no body) on Railway runs from `seed_links`; or `pipeline.py --seed-from-db --process-all`. With files, `POST /backfill` merges into `seed_links` then runs.

## Railway (current)

- **App:** https://superb-smile-production.up.railway.app — `DATABASE_URL` = Supabase **Session pooler** (aws-0-us-west-2). Procfile: `run_schema` on startup, then uvicorn. `/health` ok; `POST /sync` works. n8n **Operators Vault – Sync New Episodes** is **Active** (every 6h).

---

## How to run (once DB and network are OK)

1. **Deps** (if `pip install -r requirements.txt` hits HTTP/2 errors):
   ```powershell
   .\scripts\install_wheels.ps1
   pip install -r requirements.txt   # optional, for any extras
   ```

2. **Schema**:
   ```powershell
   python scripts/run_schema.py
   ```

3. **Seed from CSVs and process all videos** (CSVs in `%USERPROFILE%\Downloads\`):
   ```powershell
   python pipeline.py --seed-csvs --process-all
   ```
   Or store in Supabase then run from DB: `python pipeline.py --seed-csvs-to-db` then `python pipeline.py --seed-from-db --process-all`. Via API: `POST /seed-links/csv` then `POST /backfill` (no body).

4. **Single video**:
   ```powershell
   python pipeline.py --process VIDEO_ID --podcast 9operators
   ```

5. **Fetch new from YouTube** (requires `YOUTUBE_API_KEY`):
   ```powershell
   python pipeline.py --fetch-new
   python pipeline.py --fetch-new --process-new
   ```

6. **Process only unprocessed**:
   ```powershell
   python pipeline.py --process-new
   ```

7. **One-command sync**:
   ```powershell
   python scripts/run_all.py
   python scripts/run_all.py --seed-csvs
   ```

8. **API** (for n8n or HTTP):
   ```powershell
   python -m uvicorn api:app --host 0.0.0.0 --port 8000
   ```
   (Use `python -m uvicorn` if `uvicorn` is not on PATH.) `POST /process`, `POST /fetch-new`, `POST /process-new`, `POST /sync`, `POST /sync/async` (202), `POST /process-new/async` (202), `POST /backfill` (multipart), `GET /jobs/{job_id}`. `GET /health`, `GET /search?q=...&podcast=...&sort=...`, `GET /search-ui`.

9. **n8n workflows**: `python scripts/setup_n8n_workflows.py` (idempotent; sets Railway URL, activates Sync). Or `scripts/import_n8n_workflow.py` for process-only. Requires `N8N_HOST`, `N8N_API_KEY` in `.env`.

---

## Env

- `.env`: Supabase, Meilisearch, Deepgram, Anthropic, n8n, etc. `DATABASE_URL` must be set for schema and pipeline. `YOUTUBE_API_KEY` (replace `<your-youtube-api-key>`) is required for `--fetch-new` and `POST /fetch-new`. Override Finance Operators channel: `YOUTUBE_CHANNEL_FINANCE_OPERATORS=@ActualHandle`.

---

## CSV paths (youtube_client.DEFAULT_CSV_PATHS)

| Podcast            | Path                                                                 |
|--------------------|----------------------------------------------------------------------|
| 9operators         | `%USERPROFILE%\Downloads\Operators Podcast Video Youtube Links.csv`  |
| marketing_operator | `%USERPROFILE%\Downloads\Marketing Operators Podcast Video Youtube Links.csv` |
| finance_operators  | `%USERPROFILE%\Downloads\Finance Operators Podcast Video Youtube Links.csv`  |
