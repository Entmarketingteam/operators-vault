"""
Operators Vault Pipeline API – HTTP trigger for n8n or external automation.
POST /process with body { "video_id": "...", "podcast": "9operators" } (podcast optional).

Run: uvicorn api:app --host 0.0.0.0 --port 8000
For Railway: uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
"""
from __future__ import annotations

import os
import threading
import uuid
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

import tempfile
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import after dotenv
from pipeline import _fetch_new, _get_unprocessed, _process_one, run_seed_and_process_all, upsert_seed_links

app = FastAPI(title="Operators Vault Pipeline API", version="1.0.0")

# In-memory job store for async /sync and /process-new (202). Lost on restart.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class ProcessRequest(BaseModel):
    video_id: str
    podcast: str = "9operators"


class SeedLinkEntry(BaseModel):
    video_id: str
    podcast: str
    title: str = ""
    duration_seconds: int | None = None
    url: str = ""


class SeedLinksRequest(BaseModel):
    links: list[SeedLinkEntry]


@app.post("/process")
def process(req: ProcessRequest):
    """Run the pipeline for one video: audio -> transcribe -> extract -> store."""
    ok = _process_one(req.video_id, req.podcast)
    if not ok:
        raise HTTPException(status_code=500, detail="Processing failed")
    return {"ok": True, "video_id": req.video_id, "podcast": req.podcast}


def _do_upsert_seed_links(rows: list[dict]) -> int:
    """Upsert rows into seed_links. Returns count. Raises on no DATABASE_URL."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        n = upsert_seed_links(cur, rows)
        conn.commit()
        return n
    finally:
        cur.close()
        conn.close()


@app.post("/seed-links")
def seed_links(req: SeedLinksRequest):
    """Upsert links into seed_links (Supabase). Body: { \"links\": [ {\"video_id\", \"podcast\", \"title?\", \"duration_seconds?\", \"url?\"} ] }. Does not run backfill."""
    rows = [e.model_dump() for e in req.links]
    n = _do_upsert_seed_links(rows)
    return {"ok": True, "upserted": n}


@app.post("/seed-links/csv")
async def seed_links_csv(request: Request):
    """
    Upload CSVs into seed_links. Multipart form: 9operators, marketing_operator, finance_operators (file fields).
    Does not run backfill. Returns {ok, upserted}.
    """
    from youtube_client import load_all_seed_csvs
    form = await request.form()
    tmpdir = Path(tempfile.mkdtemp(prefix="seed_links_csv_"))
    paths: dict[str, str] = {}
    for key in ("9operators", "marketing_operator", "finance_operators"):
        f = form.get(key)
        if f is not None and hasattr(f, "read"):
            raw = await f.read()
            if not isinstance(raw, bytes):
                raw = (raw or "").encode("utf-8", errors="replace")
            if raw:
                p = tmpdir / f"{key}.csv"
                p.write_bytes(raw)
                paths[key] = str(p)
    if not paths:
        raise HTTPException(status_code=400, detail="Upload at least one CSV: 9operators, marketing_operator, finance_operators")
    rows = load_all_seed_csvs(paths=paths)
    n = _do_upsert_seed_links(rows)
    return {"ok": True, "upserted": n}


def _do_fetch_new() -> dict:
    """Fetch new from YouTube; returns {ok, upserted}. Raises HTTPException on env/error."""
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


def _do_sync() -> dict:
    """Run fetch-new then process-new. Returns {ok, upserted, processed, video_ids}. Raises on env/error."""
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


def _do_process_new() -> dict:
    """Process all unprocessed videos. Returns {ok, processed, video_ids}. Raises on env/error."""
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


@app.post("/fetch-new")
def fetch_new():
    """Fetch new videos from YouTube channels (9 Operators, Marketing, Finance) and upsert into videos. Requires DATABASE_URL and YOUTUBE_API_KEY."""
    return _do_fetch_new()


@app.post("/process-new")
def process_new():
    """Process all videos that have no transcription yet. Requires DATABASE_URL. Can be slow (audio download, transcribe, LLM per video)."""
    return _do_process_new()


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
def search(
    q: str = "",
    podcast: str | None = None,
    category: str | None = None,
    video_id: str | None = None,
    limit: int = 20,
    sort: str | None = None,
):
    """Search the insights vault via Meilisearch. Params: q, podcast, category, video_id, limit (default 20), sort (e.g. start_time_sec:asc or title:desc)."""
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

    opts: dict = {"limit": min(limit, 100), "filter": filter_str}
    if sort:
        parts = [s.strip() for s in sort.split(",") if s.strip()]
        if parts:
            opts["sort"] = parts

    try:
        res = idx.search(q or "", opts)
        return {"query": q or "(all)", "total": res.get("estimatedTotalHits", 0), "hits": res.get("hits", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}")


_SEARCH_UI_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Operators Vault – Search</title>
<style>
  body { font-family: system-ui,sans-serif; max-width: 720px; margin: 1.5rem auto; padding: 0 1rem; }
  input, select { padding: 0.4rem; margin: 0 0.5rem 0.5rem 0; }
  button { padding: 0.5rem 1rem; cursor: pointer; }
  .hit { border: 1px solid #eee; border-radius: 6px; padding: 0.75rem; margin: 0.5rem 0; }
  .hit h4 { margin: 0 0 0.25rem 0; }
  .meta { font-size: 0.85rem; color: #555; }
  .err { color: #c00; }
  a { color: #06c; }
</style>
</head><body>
<h1>Operators Vault – Search</h1>
<form id="f">
  <input name="q" type="search" placeholder="Search…" size="30">
  <select name="podcast"><option value="">All podcasts</option>
    <option value="9operators">9 Operators</option>
    <option value="marketing_operator">Marketing Operator</option>
    <option value="finance_operators">Finance Operators</option>
  </select>
  <input name="limit" type="number" value="20" min="1" max="100" style="width:4rem">
  <button type="submit">Search</button>
</form>
<div id="out"></div>
<script>
  document.getElementById('f').onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const params = new URLSearchParams();
    if (fd.get('q')) params.set('q', fd.get('q'));
    if (fd.get('podcast')) params.set('podcast', fd.get('podcast'));
    params.set('limit', fd.get('limit') || '20');
    const out = document.getElementById('out');
    out.innerHTML = 'Loading…';
    try {
      const r = await fetch('/search?' + params);
      const j = await r.json();
      if (!r.ok) { out.innerHTML = '<p class="err">' + (j.detail || r.status) + '</p>'; return; }
      let html = '<p><strong>' + j.total + '</strong> result(s)</p>';
      (j.hits || []).forEach(h => {
        const y = 'https://www.youtube.com/watch?v=' + (h.video_id || '');
        html += '<div class="hit"><h4>' + (h.title || '(no title)') + '</h4>';
        html += '<p class="meta">' + (h.podcast || '') + ' · ' + (h.category || '') + ' · <a href="' + y + '" target="_blank">' + (h.video_id || '') + '</a></p>';
        if (h.description) html += '<p>' + h.description + '</p>';
        html += '</div>';
      });
      out.innerHTML = html || '<p>No hits.</p>';
    } catch (err) { out.innerHTML = '<p class="err">' + err + '</p>'; }
  };
</script>
</body></html>
"""


@app.get("/search-ui", response_class=HTMLResponse)
def search_ui():
    """Simple HTML UI for GET /search. Query, podcast filter, limit."""
    return _SEARCH_UI_HTML


@app.post("/sync")
def sync():
    """Run fetch-new then process-new in one call. Good for cron/n8n. Can be slow. For 202 + job, use POST /sync/async."""
    return _do_sync()


def _run_async_job(job_id: str, fn, job_type: str):
    """Run fn() in a background thread; store result or error in _jobs[job_id]."""
    def run():
        try:
            out = fn()
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = out
        except HTTPException as e:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = f"{e.status_code}: {e.detail}"
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(e)

    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "type": job_type, "result": None, "error": None}
    t = threading.Thread(target=run, daemon=True)
    t.start()


@app.post("/sync/async")
def sync_async():
    """Like POST /sync but returns 202 Accepted with job_id. Poll GET /jobs/{job_id} for status. Good when sync is slow."""
    job_id = str(uuid.uuid4())
    _run_async_job(job_id, _do_sync, "sync")
    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "running", "jobs": f"/jobs/{job_id}"})


@app.post("/process-new/async")
def process_new_async():
    """Like POST /process-new but returns 202 Accepted with job_id. Poll GET /jobs/{job_id} for status."""
    job_id = str(uuid.uuid4())
    _run_async_job(job_id, _do_process_new, "process-new")
    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "running", "jobs": f"/jobs/{job_id}"})


@app.post("/backfill")
async def backfill(request: Request):
    """
    Run backfill from seed_links (Supabase): seed into videos then process unprocessed.
    - With form files (9operators, marketing_operator, finance_operators): parse CSVs, upsert into seed_links, then run.
    - With no files: run from existing seed_links. Use POST /seed-links or /seed-links/csv first to store links.
    Returns 202 + job_id; poll GET /jobs/{job_id}.
    """
    from youtube_client import load_all_seed_csvs

    form = await request.form()
    tmpdir = Path(tempfile.mkdtemp(prefix="backfill_"))
    paths: dict[str, str] = {}
    for key in ("9operators", "marketing_operator", "finance_operators"):
        f = form.get(key)
        if f is not None and hasattr(f, "read"):
            raw = await f.read()
            if not isinstance(raw, bytes):
                raw = (raw or "").encode("utf-8", errors="replace")
            if raw:
                p = tmpdir / f"{key}.csv"
                p.write_bytes(raw)
                paths[key] = str(p)

    job_id = str(uuid.uuid4())

    def run():
        try:
            if paths:
                rows = load_all_seed_csvs(paths=paths)
                out = run_seed_and_process_all(seed_link_rows=rows)
            else:
                out = run_seed_and_process_all(from_db=True)
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = {"ok": True, **out}
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(e)

    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "type": "backfill", "result": None, "error": None}
    threading.Thread(target=run, daemon=True).start()
    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "running", "jobs": f"/jobs/{job_id}"})


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Status of an async job (sync/async, process-new/async, backfill). status: running | done | error."""
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    out = {"job_id": job_id, "status": j["status"], "type": j.get("type")}
    if j.get("result") is not None:
        out["result"] = j["result"]
    if j.get("error") is not None:
        out["error"] = j["error"]
    return out


@app.get("/")
def root():
    return {
        "service": "Operators Vault Pipeline API",
        "docs": "/docs",
        "health": "/health",
        "search": "/search",
        "search_ui": "/search-ui",
        "sync": "POST /sync",
        "sync_async": "POST /sync/async (202 + job)",
        "process_new_async": "POST /process-new/async (202 + job)",
        "seed_links": "POST /seed-links (JSON), POST /seed-links/csv (multipart) — store links in Supabase seed_links",
        "backfill": "POST /backfill (optional multipart CSVs; or none to run from seed_links in DB; 202 + job)",
        "jobs": "GET /jobs/{job_id}",
    }
