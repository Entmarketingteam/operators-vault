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
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Import after dotenv
from pipeline import _fetch_new, _get_unprocessed, _process_one, run_seed_and_process_all, upsert_seed_links

app = FastAPI(title="Operators Vault Pipeline API", version="1.0.0")

# CORS so Vercel (and other) front ends can call /search
_cors_origins = os.environ.get("CORS_ORIGINS", "*").strip()
_origins_list = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins_list,
    allow_credentials=(_origins_list != ["*"]),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.mount("/static", StaticFiles(directory=str(_root / "static")), name="static")


def _render_search_ui() -> str:
    path = _root / "templates" / "search.html"
    if not path.exists():
        return "<!DOCTYPE html><html><body><h1>Operators Vault</h1><p>Template not found.</p></body></html>"
    html = path.read_text(encoding="utf-8")
    return html.replace("{{ static_prefix }}", "/static").replace("{{ api_base }}", "").replace("{{ request.url_for('search_ui') }}", "/search-ui")
_security = HTTPBearer(auto_error=False)


def _verify_supabase_jwt(credentials: HTTPAuthorizationCredentials | None = Depends(_security)):
    """Require valid Supabase JWT for private search. Set SUPABASE_JWT_SECRET in env."""
    secret = os.environ.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="SUPABASE_JWT_SECRET not configured")
    if not credentials or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="Authorization required (Bearer token from Supabase Auth)")
    try:
        import jwt
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False},
        )
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

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
    """Check env and connectivity: database, youtube, deepgram, anthropic. Search is Postgres FTS (no Meilisearch)."""
    checks: dict[str, str] = {}
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
    checks["search"] = "postgres"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


def _search_postgres(
    q: str,
    podcast: str | None = None,
    category: str | None = None,
    video_id: str | None = None,
    limit: int = 20,
    type_: str = "insights",
) -> dict:
    """Run Postgres FTS search (search_insights and/or search_moments). Returns {query, total, hits}."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 100)
    hits: list[dict] = []
    if type_ in ("insights", "all") and q and q.strip():
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec, rank, headline_title, headline_description FROM search_insights(%s, %s, 0, %s, %s, %s)",
                (q.strip(), limit, podcast, category, video_id),
            )
            for row in cur.fetchall():
                hits.append({
                    "type": "insight",
                    "id": str(row[0]),
                    "video_id": row[1],
                    "podcast": row[2],
                    "category": row[3],
                    "title": row[4],
                    "description": row[5],
                    "start_time_sec": float(row[6]) if row[6] is not None else None,
                    "end_time_sec": float(row[7]) if row[7] is not None else None,
                    "rank": float(row[8]) if row[8] is not None else 0,
                    "headline_title": row[9],
                    "headline_description": row[10],
                })
        finally:
            cur.close()
            conn.close()
    if type_ in ("moments", "all") and q and q.strip():
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, video_id, podcast, start_time_sec, end_time_sec, text, speaker_label, rank, headline FROM search_moments(%s, %s, 0, %s, %s)",
                (q.strip(), limit, podcast, video_id),
            )
            for row in cur.fetchall():
                hits.append({
                    "type": "moment",
                    "id": str(row[0]),
                    "video_id": row[1],
                    "podcast": row[2],
                    "start_time_sec": float(row[3]) if row[3] is not None else None,
                    "end_time_sec": float(row[4]) if row[4] is not None else None,
                    "text": row[5],
                    "speaker_label": row[6],
                    "rank": float(row[7]) if row[7] is not None else 0,
                    "headline": row[8],
                })
        finally:
            cur.close()
            conn.close()
    if type_ == "all" and hits:
        hits.sort(key=lambda h: h.get("rank") or 0, reverse=True)
        hits = hits[:limit]
    return {"query": q or "(all)", "total": len(hits), "hits": hits}


@app.get("/search")
def search(
    q: str = "",
    podcast: str | None = None,
    category: str | None = None,
    video_id: str | None = None,
    limit: int = 20,
    type_: str = "insights",
    _: dict = Depends(_verify_supabase_jwt),
):
    """Search insights and/or timestamp moments via Postgres FTS. Requires Bearer token (Supabase Auth). Params: q, podcast, category, video_id, limit, type=insights|moments|all."""
    return _search_postgres(q, podcast=podcast, category=category, video_id=video_id, limit=limit, type_=type_)


@app.get("/search-ui", response_class=HTMLResponse)
def search_ui():
    """Search UI: sign in (token), filters, and result cards. Uses templates/search.html and static assets."""
    return _render_search_ui()


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


@app.get("/stats")
def stats():
    """Vault index status: per-podcast counts of videos in DB, processed (have transcription), and unprocessed. Use to see if 9 Operators / Marketing Operator are fully pulled and indexed."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=15)
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT v.podcast,
                       COUNT(*) AS videos,
                       COUNT(t.id) AS processed
                FROM videos v
                LEFT JOIN transcriptions t ON t.video_id = v.video_id
                GROUP BY v.podcast
                ORDER BY v.podcast
                """
            )
            rows = cur.fetchall()
            by_podcast = {}
            for podcast, videos, processed in rows:
                by_podcast[podcast] = {
                    "videos": videos,
                    "processed": processed,
                    "unprocessed": videos - processed,
                    "all_indexed": videos > 0 and processed == videos,
                }
            try:
                cur.execute("SELECT podcast, COUNT(*) FROM seed_links GROUP BY podcast ORDER BY podcast")
                seed_rows = cur.fetchall()
                seed_by_podcast = {p: c for p, c in seed_rows}
                for p in by_podcast:
                    by_podcast[p]["seed_links"] = seed_by_podcast.get(p, 0)
            except Exception:
                for p in by_podcast:
                    by_podcast[p]["seed_links"] = 0
            return {"by_podcast": by_podcast}
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {e!s}")


@app.get("/")
def root():
    return {
        "service": "Operators Vault Pipeline API",
        "docs": "/docs",
        "health": "/health",
        "stats": "/stats",
        "search": "/search",
        "search_ui": "/search-ui",
        "sync": "POST /sync",
        "sync_async": "POST /sync/async (202 + job)",
        "process_new_async": "POST /process-new/async (202 + job)",
        "seed_links": "POST /seed-links (JSON), POST /seed-links/csv (multipart) — store links in Supabase seed_links",
        "backfill": "POST /backfill (optional multipart CSVs; or none to run from seed_links in DB; 202 + job)",
        "jobs": "GET /jobs/{job_id}",
    }
