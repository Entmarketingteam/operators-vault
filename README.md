# Operators Vault

DTC operator knowledge base: podcast transcripts (9 Operators, Marketing Operator, Finance
Operator, TITANS) **and** newsletter/article archives (Nik Sharma, Taylor Holiday/CTC, Chase
Dimond, and others) — extracted into a searchable, RAG-queryable vault.

**For current app state — what's live, what broke and why, deploy commands, credentials,
architecture — read [`CLAUDE.md`](./CLAUDE.md). It is the maintained source of truth.** This
file is intentionally a short pointer, not a duplicate.

## What's here

- **`api.py`** — FastAPI backend (Railway). Search, insight extraction, topic guides, chat/RAG,
  newsletter + CTC article ingestion, job orchestration.
- **`frontend/`** — Next.js app (Vercel: `operators-vault.vercel.app`). The live frontend.
- **`pipeline.py`** — CLI orchestrator for video/newsletter/article ingestion.
- **`docs/specs/`** — current design specs for the ingestion pipeline (audio, extraction schema,
  speaker attribution, scoring, syndication, CTC articles).
- **`archive/`** — historical docs and the retired static `web/` frontend, kept for reference.
  Superseded by `CLAUDE.md` and `frontend/` respectively — do not treat anything under
  `archive/` as describing current behavior.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Copy `.env.local` / `.env` and fill in real values — `DATABASE_URL` (Supabase), `ANTHROPIC_API_KEY`,
`DEEPGRAM_API_KEY`, `YOUTUBE_API_KEY`, `SUPABASE_JWT_SECRET`. See `CLAUDE.md` for what each
integration is for and current gotchas.

Run the API locally:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Run the frontend locally:
```bash
cd frontend && npm install && npm run dev
```

## Deploying

See `CLAUDE.md` → **Deploy Commands**. Short version: push to `master` to deploy the backend
(Railway auto-deploys); build and deploy `frontend/` explicitly via the Vercel CLI for the
frontend. Sync is driven by scheduled n8n workflows (see `CLAUDE.md` → **n8n Workflows**), not a
Railway cron endpoint.
