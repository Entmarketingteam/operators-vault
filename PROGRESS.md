# Operators Vault – Progress Checkpoint

**Saved:** Local snapshot of current state.

---

## Done

- **Schema** (`sql/schema.sql`): `videos`, `transcriptions`, `segments`, `insights`, `people`, `video_people` with `channel_id` and `published_at` on `videos`.
- **run_schema.py**: Applies schema; loads `.env` via `python-dotenv` or manual fallback.
- **youtube_client.py**: `load_from_csv`, `load_all_seed_csvs`, `resolve_channel_id`, `fetch_channel_videos`; CSV paths in `USERPROFILE\Downloads`.
- **pipeline.py**: `--seed-csvs`, `--seed-csvs --process-all`, `--process VIDEO_ID [--podcast ...]`; `.env` fallback.
- **api.py**: FastAPI `POST /process`, `GET /`; `.env` fallback.
- **Prompts**: `extract_insights_system`, `make_framework_content`, `timestamp_extraction`, `title_generation` under `prompts/operators/`.
- **n8n**: `n8n-workflow.json`; `scripts/import_n8n_workflow.py` to import via API.
- **Deps workaround**: `scripts/install_wheels.ps1` downloads wheels from PyPI via `Invoke-WebRequest` and runs `pip install --no-deps` (avoids pip HTTP/2 errors). `wheels/` holds cached wheels.
- **psycopg2-binary**: Installed from a manually downloaded wheel (pip had HTTP/2 issues with PyPI). Other deps can be installed via `install_wheels.ps1` or `pip install -r requirements.txt` when the network allows.

---

## Not done / Blocked

- **Schema apply**: `python scripts/run_schema.py` failed with `could not translate host name "db.wbdwnlzbgugewtmvahwg.supabase.co" to address` (DNS/network; DB not reachable from this machine).
- **Seed + process-all**: Not run; depends on DB and full deps. Pipeline needs: `yt-dlp`, `deepgram-sdk`, `anthropic`, `meilisearch`, `python-dotenv`, and their deps.
- **YouTube `--fetch-new` / `--process-new`**: Not implemented in `pipeline.py`; `youtube_client` has `resolve_channel_id` and `fetch_channel_videos` ready.

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

5. **API** (for n8n or HTTP):
   ```powershell
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```
   Then `POST /process` with `{"video_id":"...","podcast":"9operators"}`.

6. **n8n workflow**:
   ```powershell
   python scripts/import_n8n_workflow.py
   ```
   (Requires `N8N_HOST` and `N8N_API_KEY` in `.env`.)

---

## Env

- `.env`: Supabase, Meilisearch, Deepgram, Anthropic, n8n, etc. `DATABASE_URL` must be set for schema and pipeline. `YOUTUBE_API_KEY` still has placeholder `<your-youtube-api-key>` for `fetch_channel_videos` / `resolve_channel_id`.

---

## CSV paths (youtube_client.DEFAULT_CSV_PATHS)

| Podcast            | Path                                                                 |
|--------------------|----------------------------------------------------------------------|
| 9operators         | `%USERPROFILE%\Downloads\Operators Podcast Video Youtube Links.csv`  |
| marketing_operator | `%USERPROFILE%\Downloads\Marketing Operators Podcast Video Youtube Links.csv` |
| finance_operators  | `%USERPROFILE%\Downloads\Finance Operators Podcast Video Youtube Links.csv`  |
