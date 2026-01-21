# Operators Vault – Developer / Agent Handoff

**Read this first when picking up in a new session.** Repo: https://github.com/Entmarketingteam/operators-vault

---

## 1. What This Project Is

Podcast intelligence for **9 Operators**, **Marketing Operator**, **Finance Operator**: YouTube → audio → Deepgram transcription → LLM insight extraction (Anthropic) → Supabase + Meilisearch. CSVs seed initial videos; `--fetch-new` pulls new episodes from YouTube channels; `--process-new` runs the pipeline on unprocessed videos.

---

## 2. Where We Are (Current State)

- **Implemented and committed:** Schema, pipeline (seed, process, fetch-new, process-new), API (process, fetch-new, process-new, sync, health, search), youtube_client (CSVs + YouTube Data API), prompts, run_schema, run_all, n8n workflows, install_wheels workaround.
- **.env:** `DATABASE_URL`, `YOUTUBE_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `MEILISEARCH_*`, `N8N_*` are set. `.env` is gitignored.
- **Not yet run in this environment:** `run_schema` (DB was unreachable: DNS to Supabase). `--seed-csvs --process-all` and `run_all` not executed (depend on DB + full deps). On a machine with DB + Meilisearch + internet, the intended flow works.

---

## 3. Repo and Local Paths

- **Git:** https://github.com/Entmarketingteam/operators-vault (origin over HTTPS). Branch: `master`.
- **Local project root:** `C:\Users\ethan.atchley\operators-vault`
- **Key files:**
  - `PLAN.md` – Plan + status + next steps (keep this open as the “plan”)
  - `PROGRESS.md` – Done / Not done / How to run / Env / CSV paths
  - `README.md` – Setup and usage
  - `HANDOFF.md` – This file
  - `api.py` – FastAPI app
  - `pipeline.py` – CLI: --seed-csvs, --process-all, --process, --fetch-new, --process-new
  - `youtube_client.py` – CSVs + resolve_channel_id, fetch_channel_videos
  - `scripts/run_schema.py` – Apply `sql/schema.sql`
  - `scripts/run_all.py` – schema + fetch-new + process-new (optional --seed-csvs)

---

## 4. Environment and Secrets

- **`.env`** in project root (gitignored). Contains: `DATABASE_URL`, `YOUTUBE_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `MEILISEARCH_HOST`, `MEILISEARCH_API_KEY`, `N8N_HOST`, `N8N_API_KEY`, `DATABASE_URL` (Supabase Postgres), etc.
- **Deps:** `pip install -r requirements.txt`. If pip hits HTTP/2 errors: `.\scripts\install_wheels.ps1` then `pip install -r requirements.txt`. `yt-dlp` must be on PATH or from the yt-dlp Python package.

---

## 5. Commands to Run (Once DB and Network Work)

```powershell
cd C:\Users\ethan.atchley\operators-vault
# Deps (if needed)
.\scripts\install_wheels.ps1
pip install -r requirements.txt

# Schema
python scripts/run_schema.py

# One-command sync (fetch from YouTube + process new)
python scripts/run_all.py

# Or with CSV seed first
python scripts/run_all.py --seed-csvs

# API
python -m uvicorn api:app --host 0.0.0.0 --port 8000
# Then: GET /health, GET /search?q=..., POST /sync, POST /process, etc.
```

---

## 6. Instructions for a New Agent (Cursor / Full-Context Window)

1. **Open:** `C:\Users\ethan.atchley\operators-vault` and read, in order: `HANDOFF.md`, `PLAN.md`, `PROGRESS.md`.
2. **Context:** The pipeline is built. Pending: run `run_schema`, then `run_all` or `--seed-csvs --process-all` when DB and Meilisearch are reachable. `YOUTUBE_API_KEY` is set in `.env`.
3. **If the user says “keep building”:** Prefer (a) running and validating the existing flow (schema, run_all, /health, /search), (b) fixing Finance Operators channel handle if wrong (`YOUTUBE_CHANNEL_FINANCE_OPERATORS`), (c) extending API or pipeline per `PLAN.md` “Next steps”.
4. **If the user reports errors:** Use `GET /health` and `scripts/run_schema.py` / `pipeline.py --fetch-new` for diagnosis. Check `.env` and that `yt-dlp` is available for `audio_extractor`.

---

## 7. CSV Paths (for --seed-csvs)

| Podcast            | Default path                                                                 |
|--------------------|------------------------------------------------------------------------------|
| 9operators         | `%USERPROFILE%\Downloads\Operators Podcast Video Youtube Links.csv`          |
| marketing_operator | `%USERPROFILE%\Downloads\Marketing Operators Podcast Video Youtube Links.csv`|
| finance_operators  | `%USERPROFILE%\Downloads\Finance Operators Podcast Video Youtube Links.csv`  |

---

## 8. n8n

- `n8n-workflow.json` – One-off: Manual/Webhook → Set (video_id, podcast) → `POST /process`.
- `n8n-workflow-fetch-new.json` – Cron every 6h → `POST /sync`.
- Import in n8n; set HTTP node URL to the Pipeline API (e.g. `https://your-app.railway.app/process` or `/sync`). `scripts/import_n8n_workflow.py` imports the process workflow via N8N API.
