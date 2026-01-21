"""
Operators Vault Pipeline API – HTTP trigger for n8n or external automation.
POST /process with body { "video_id": "...", "podcast": "9operators" } (podcast optional).

Run: uvicorn api:app --host 0.0.0.0 --port 8000
For Railway: uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
"""
from __future__ import annotations

import os
from pathlib import Path

_root = Path(__file__).resolve().parent
_env = _root / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env)
except ImportError:
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip():
                    os.environ.setdefault(k.strip(), v.strip())

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import after dotenv
from pipeline import _fetch_new, _get_unprocessed, _process_one

app = FastAPI(title="Operators Vault Pipeline API", version="1.0.0")


class ProcessRequest(BaseModel):
    video_id: str
    podcast: str = "9operators"


@app.post("/process")
def process(req: ProcessRequest):
    """Run the pipeline for one video: audio -> transcribe -> extract -> store."""
    ok = _process_one(req.video_id, req.podcast)
    if not ok:
        raise HTTPException(status_code=500, detail="Processing failed")
    return {"ok": True, "video_id": req.video_id, "podcast": req.podcast}


@app.post("/fetch-new")
def fetch_new():
    """Fetch new videos from YouTube channels (9 Operators, Marketing, Finance) and upsert into videos. Requires DATABASE_URL and YOUTUBE_API_KEY."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    if not os.environ.get("YOUTUBE_API_KEY"):
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY not set")
    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        n = _fetch_new(cur)
        conn.commit()
        return {"ok": True, "upserted": n}
    finally:
        cur.close()
        conn.close()


@app.post("/process-new")
def process_new():
    """Process all videos that have no transcription yet. Requires DATABASE_URL. Can be slow (audio download, transcribe, LLM per video)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    rows = _get_unprocessed(cur)
    cur.close()
    conn.close()
    processed = []
    for vid, pod in rows:
        ok = _process_one(vid, pod)
        if ok:
            processed.append(vid)
    return {"ok": True, "processed": len(processed), "video_ids": processed}


@app.get("/health")
def health():
    """Check env and connectivity: database, youtube, meilisearch, deepgram, anthropic. Returns 200 with status dict."""
    checks: dict[str, str] = {}
    # Database
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        checks["database"] = "missing"
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            conn.close()
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e!s}"

    checks["youtube"] = "ok" if os.environ.get("YOUTUBE_API_KEY") else "missing"
    checks["deepgram"] = "ok" if os.environ.get("DEEPGRAM_API_KEY") else "missing"
    checks["anthropic"] = "ok" if os.environ.get("ANTHROPIC_API_KEY") else "missing"

    ms_host = os.environ.get("MEILISEARCH_HOST")
    ms_key = os.environ.get("MEILISEARCH_API_KEY")
    if not ms_host or not ms_key:
        checks["meilisearch"] = "missing"
    else:
        try:
            from meilisearch import Client as MeiliClient
            c = MeiliClient(ms_host, ms_key)
            c.health()
            checks["meilisearch"] = "ok"
        except Exception as e:
            checks["meilisearch"] = f"error: {e!s}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@app.get("/search")
def search(q: str = "", podcast: str | None = None, category: str | None = None, video_id: str | None = None, limit: int = 20):
    """Search the insights vault via Meilisearch. Query params: q (search text), podcast, category, video_id, limit (default 20)."""
    ms_host = os.environ.get("MEILISEARCH_HOST")
    ms_key = os.environ.get("MEILISEARCH_API_KEY")
    if not ms_host or not ms_key:
        raise HTTPException(status_code=503, detail="MEILISEARCH_HOST or MEILISEARCH_API_KEY not set")
    try:
        from meilisearch import Client as MeiliClient
        idx = MeiliClient(ms_host, ms_key).index("operators_insights")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Meilisearch: {e!s}")

    filters: list[str] = []
    if podcast:
        filters.append(f'podcast = "{podcast}"')
    if category:
        filters.append(f'category = "{category}"')
    if video_id:
        filters.append(f'video_id = "{video_id}"')
    filter_str = " AND ".join(filters) if filters else None

    try:
        res = idx.search(q or "", {"limit": min(limit, 100), "filter": filter_str})
        return {"query": q or "(all)", "total": res.get("estimatedTotalHits", 0), "hits": res.get("hits", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}")


@app.post("/sync")
def sync():
    """Run fetch-new then process-new in one call. Good for cron/n8n. Can be slow."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    if not os.environ.get("YOUTUBE_API_KEY"):
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY not set")
    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    upserted = _fetch_new(cur)
    conn.commit()
    rows = _get_unprocessed(cur)
    cur.close()
    conn.close()

    processed = []
    for vid, pod in rows:
        ok = _process_one(vid, pod)
        if ok:
            processed.append(vid)
    return {"ok": True, "upserted": upserted, "processed": len(processed), "video_ids": processed}


@app.get("/")
def root():
    return {"service": "Operators Vault Pipeline API", "docs": "/docs", "health": "/health", "search": "/search", "sync": "POST /sync"}
