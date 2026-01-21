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
   Required for the pipeline: `DATABASE_URL`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`. For Meilisearch: `MEILISEARCH_HOST`, `MEILISEARCH_API_KEY`. For n8n import: `N8N_HOST`, `N8N_API_KEY`.

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

**Pipeline API (for n8n or automation):**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
Then `POST http://localhost:8000/process` with body `{"video_id": "VIDEO_ID", "podcast": "9operators"}`.

**n8n:**  
- **Import via script** (after setting `N8N_HOST` and `N8N_API_KEY` in `.env`): `python scripts/import_n8n_workflow.py`  
- Or import `n8n-workflow.json` manually in [entagency](https://entagency.app.n8n.cloud).  
In the HTTP Request node, set the URL to your Pipeline API (e.g. `https://your-app.railway.app/process`). To process from a Webhook: add a Webhook trigger and change the Set node to `{{ $json.body.video_id }}` and `{{ $json.body.podcast }}`.

## Project layout

- `sql/schema.sql` – Supabase schema
- `scripts/run_schema.py` – Apply schema (uses `DATABASE_URL` from `.env`)
- `scripts/import_n8n_workflow.py` – Import `n8n-workflow.json` to n8n via API (`N8N_HOST`, `N8N_API_KEY`)
- `youtube_client.py` – Fetch from channels or parse CSVs
- `audio_extractor.py` – Download audio (yt-dlp)
- `deepgram_client.py` – Transcribe with diarization
- `insight_extractor.py` – LLM extraction (Anthropic, Operators prompts)
- `pipeline.py` – Orchestrator
- `api.py` – FastAPI server for n8n / HTTP trigger (`POST /process`)
- `n8n-workflow.json` – n8n workflow to trigger the pipeline API
- `prompts/operators/` – Insight, title, timestamp, framework prompts
- `meilisearch-setup.md` – Index config
