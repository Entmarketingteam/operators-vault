# Operators Vault – Progress Checkpoint

**For new agent / developer:** Read **HANDOFF.md** first, then **PLAN.md**. This file is the detailed “Done / Not done / How to run.”

---

## Done

- **Schema** (`sql/schema.sql`): `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people` with `channel_id` and `published_at` on `videos`.
- **run_schema.py**: Applies schema; loads `.env` via `python-dotenv` or manual fallback.
- **youtube_client.py**: `load_from_csv`, `load_all_seed_csvs`, `resolve_channel_id`, `fetch_channel_videos` (returns `published_at`), `get_channel_handle`; `DEFAULT_CHANNEL_HANDLES` (9operators→Operators9, marketing_operator→MarketingOperators, finance_operators→FinanceOperators). Override via `YOUTUBE_CHANNEL_<PODCAST>`. CSV paths in `USERPROFILE\Downloads`.
- **pipeline.py**: `--seed-csvs`, `--seed-csvs --process-all`, `--process VIDEO_ID [--podcast ...]`, `--fetch-new`, `--process-new`, `--fetch-new --process-new`; `.env` fallback. `_ensure_video` supports `channel_id`, `published_at`.
- **api.py**: FastAPI `POST /process`, `POST /fetch-new`, `POST /process-new`, `POST /sync`, `GET /health`, `GET /search`, `GET /`; `.env` fallback.
- **Prompts**: `extract_insights_system`, `make_framework_content`, `timestamp_extraction`, `title_generation` under `prompts/operators/`.
- **n8n**: `n8n-workflow.json`, `n8n-workflow-fetch-new.json` (cron → `/sync`); `scripts/import_n8n_workflow.py`.
- **scripts/run_all.py**: One-command: schema, optional `--seed-csvs`, fetch-new, process-new; `--schema-only`.
- **Deps workaround**: `scripts/install_wheels.ps1` downloads wheels from PyPI via `Invoke-WebRequest` and runs `pip install --no-deps` (avoids pip HTTP/2 errors). `wheels/` holds cached wheels. Includes: `click`, `annotated_doc`, `pydantic_core`, `typing_inspection`, `annotated_types`, `requests`, `urllib3`, `camel-converter` (FastAPI/uvicorn/meilisearch deps).
- **psycopg2-binary**: Installed from a manually downloaded wheel (pip had HTTP/2 issues with PyPI). Other deps can be installed via `install_wheels.ps1` or `pip install -r requirements.txt` when the network allows.

---

## Not done / Blocked

- **Schema apply**: `python scripts/run_schema.py` fails with `could not translate host name "db.wbdwnlzbgugewtmvahwg.supabase.co" to address` (DNS/network; DB not reachable from this machine).
- **Seed + process-all**: Not run; depends on DB and full deps.
- **API /health**: Runs; returns `status: degraded` when database or meilisearch unreachable, with per-service `checks` (database, youtube, deepgram, anthropic, meilisearch).

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
   (Use `python -m uvicorn` if `uvicorn` is not on PATH.) `POST /process`, `POST /fetch-new`, `POST /process-new`, `POST /sync`. `GET /health`, `GET /search?q=...&podcast=...`.

9. **n8n workflow**:
   ```powershell
   python scripts/import_n8n_workflow.py
   ```
   Import `n8n-workflow-fetch-new.json` for cron sync (every 6h → `POST /sync`). (Requires `N8N_HOST` and `N8N_API_KEY` in `.env`.)

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
