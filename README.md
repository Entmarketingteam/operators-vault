# Operators Vault

Podcast intelligence platform for **9 Operators**, **Marketing Operator**, and **Finance Operator**: transcriptions, insight extraction, searchable vault (Supabase + Meilisearch).

## Setup

1. **Python 3.10+** and a virtualenv:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Environment:** A `.env` file exists with placeholders. Replace them with your real keys:
   - `DATABASE_URL` — Supabase → [Database → Connect](https://supabase.com/dashboard/project/wbdwnlzbgugewtmvahwg/settings/database) → URI → Direct; replace `[YOUR-PASSWORD]` with your DB password.
   - `SUPABASE_SERVICE_ROLE_KEY`, `MEILISEARCH_API_KEY`, `YOUTUBE_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `N8N_API_KEY` — use the values you have from the plan / your dashboards.
   Required for the pipeline: `DATABASE_URL`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`. For `--fetch-new` and `POST /fetch-new`: `YOUTUBE_API_KEY`. For Meilisearch: `MEILISEARCH_HOST`, `MEILISEARCH_API_KEY`. For n8n import: `N8N_HOST`, `N8N_API_KEY`. Override YouTube channel handles: `YOUTUBE_CHANNEL_FINANCE_OPERATORS=@Handle` (default: `FinanceOperators`).

3. **Supabase:** Create a project, add `DATABASE_URL` to `.env`, then run:
   ```bash
   python scripts/run_schema.py
   ```
   Or: `psql "$DATABASE_URL" -f sql/schema.sql`. Or run `sql/schema.sql` in the Supabase SQL Editor.

4. **Meilisearch:** Create an index per `meilisearch-setup.md` or run the pipeline (it will create the index if missing).

## Usage

**Process a single video:**
```bash
python pipeline.py --process VIDEO_ID
```

**Seed from CSVs** (9 Operators, Marketing Operator, Finance Operator):
```bash
python pipeline.py --seed-csvs
```

**Process all videos from seed CSVs:**
```bash
python pipeline.py --seed-csvs --process-all
```

**Fetch new videos from YouTube channels** (9 Operators, Marketing, Finance; requires `YOUTUBE_API_KEY`):
```bash
python pipeline.py --fetch-new
python pipeline.py --fetch-new --process-new   # fetch then process unprocessed
```

**Process only videos that have no transcription yet:**
```bash
python pipeline.py --process-new
```

**One-command sync** (schema + fetch-new + process-new):
```bash
python scripts/run_all.py
python scripts/run_all.py --seed-csvs   # include CSV seed before fetch
python scripts/run_all.py --schema-only # only apply schema
```

**Pipeline API (for n8n or automation):**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
- `POST /process` — body `{"video_id": "VIDEO_ID", "podcast": "9operators"}`  
- `POST /fetch-new` — fetch from YouTube channels and upsert into `videos`  
- `POST /process-new` — process all videos with no transcription yet  
- `POST /sync` — run fetch-new then process-new in one call (for cron)  
- `GET /health` — env and connectivity checks (database, youtube, meilisearch, deepgram, anthropic)  
- `GET /search?q=...&podcast=9operators&category=...&video_id=...&limit=20` — search the insights vault via Meilisearch  

**n8n:**  
- **Import via script** (after setting `N8N_HOST` and `N8N_API_KEY` in `.env`): `python scripts/import_n8n_workflow.py`  
- Import `n8n-workflow.json` (one-off process) or `n8n-workflow-fetch-new.json` (cron: every 6h `POST /sync`) in [entagency](https://entagency.app.n8n.cloud).  
In the HTTP Request node, set the URL to your Pipeline API (e.g. `https://your-app.railway.app/process` or `/sync`). To process from a Webhook: add a Webhook trigger and change the Set node to `{{ $json.body.video_id }}` and `{{ $json.body.podcast }}`.

## Project layout

- `PLAN.md` – Plan, status, next steps (handoff)
- `HANDOFF.md` – Developer/agent handoff; read first in a new session
- `PROGRESS.md` – Done / Not done / How to run
- `sql/schema.sql` – Supabase schema
- `scripts/run_schema.py` – Apply schema (uses `DATABASE_URL` from `.env`)
- `scripts/import_n8n_workflow.py` – Import `n8n-workflow.json` to n8n via API (`N8N_HOST`, `N8N_API_KEY`)
- `youtube_client.py` – Fetch from channels or parse CSVs
- `audio_extractor.py` – Download audio (yt-dlp)
- `deepgram_client.py` – Transcribe with diarization
- `insight_extractor.py` – LLM extraction (Anthropic, Operators prompts)
- `pipeline.py` – Orchestrator
- `api.py` – FastAPI: `POST /process`, `POST /fetch-new`, `POST /process-new`, `POST /sync`, `GET /health`, `GET /search`
- `n8n-workflow.json` – n8n: one-off process video
- `n8n-workflow-fetch-new.json` – n8n: cron every 6h, `POST /sync`
- `scripts/run_all.py` – one-command: schema, optional --seed-csvs, fetch-new, process-new
- `prompts/operators/` – Insight, title, timestamp, framework prompts
- `meilisearch-setup.md` – Index config
