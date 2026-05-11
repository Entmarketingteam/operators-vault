"""
Operators Vault Pipeline API – HTTP trigger for n8n or external automation.
POST /process with body { "video_id": "...", "podcast": "9operators" } (podcast optional).

Run: uvicorn api:app --host 0.0.0.0 --port 8000
For Railway: uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
"""
from __future__ import annotations

import atexit
import contextlib
import io
import logging
import os
import signal
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
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

import requests
import tempfile
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Structured logging (import early so all modules get JSON logs)
from structured_logger import get_logger, log_job_event

_log = get_logger("api")

# Import after dotenv
from deepgram_client import DeepgramAuthError, check_api_key
from pipeline import _fetch_new, _get_unprocessed, _process_one, run_seed_and_process_all, upsert_seed_links

app = FastAPI(title="Operators Vault Pipeline API", version="2.0.0")

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


# ---------------------------------------------------------------------------
# Startup / Shutdown lifecycle
# ---------------------------------------------------------------------------
def _run_startup_migration() -> None:
    """Run add_channel_configs.sql and add_speaker_profiles.sql on startup. Idempotent."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return
    import psycopg2
    for migration_name in (
        "add_channel_configs.sql",
        "add_speaker_profiles.sql",
        "add_host_fields.sql",
        "migrate_newsletter_retry.sql",
    ):
        migration_path = _root / "sql" / migration_name
        if not migration_path.exists():
            _log.warning("startup_migration_missing", extra={"path": str(migration_path)})
            continue
        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                sql = migration_path.read_text(encoding="utf-8")
                # Execute each statement separated by semicolons, skip blank/comment-only
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        cur.execute(stmt)
            conn.close()
            _log.info("startup_migration_ok", extra={"file": migration_name})
        except Exception as e:
            _log.warning("startup_migration_failed", extra={"file": migration_name, "error": str(e)})


@app.on_event("startup")
def _on_startup():
    _log.info("Container starting", extra={
        "worker_id": _worker_id,
        "version": app.version,
        "pid": os.getpid(),
    })
    # Run DB migrations for new config tables (idempotent)
    _run_startup_migration()
    # Mark any stale running jobs as failed (from a previous container instance)
    _mark_stale_jobs_failed()
    # Auto-start newsletter workers and re-queue any unprocessed newsletters
    _ensure_newsletter_worker()
    try:
        from newsletter_ingestor import _db_conn
        conn = _db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, source, body_text FROM newsletters WHERE processed = FALSE AND body_text IS NOT NULL LIMIT 500")
            rows = cur.fetchall()
        conn.close()
        for row in rows:
            _newsletter_extract_queue.put((str(row[0]), row[1], row[2]))
        if rows:
            _log.info("newsletter_requeue_on_startup", extra={"count": len(rows)})
    except Exception as e:
        _log.warning("newsletter_requeue_failed", extra={"error": str(e)})


@app.on_event("shutdown")
def _on_shutdown():
    _log.info("Container shutting down", extra={"worker_id": _worker_id})
    _shutting_down.set()
    # Mark all currently running jobs as failed due to shutdown
    with _jobs_lock:
        for jid, j in _jobs.items():
            if j.get("status") == "running":
                j["status"] = "error"
                j["error"] = "Container shutdown while job was running"
                j["updated_at"] = time.time()
                log_job_event(jid, "failed", {"type": j.get("type"), "reason": "shutdown"})
    _log.info("Shutdown complete, all running jobs marked failed", extra={"worker_id": _worker_id})


def _handle_signal(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    _log.warning("Received signal %s, initiating graceful shutdown", sig_name, extra={"worker_id": _worker_id})
    _shutting_down.set()


# Register signal handlers (best-effort; may fail in non-main thread)
try:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
except (ValueError, OSError):
    pass  # not in main thread


def _public_config() -> dict:
    """Public config from env (for GET /config and search UI). All editable in Railway/Vercel."""
    api_base = (os.environ.get("PUBLIC_API_BASE") or "").strip().rstrip("/")
    return {
        "apiBase": api_base,
        "supabaseUrl": (os.environ.get("SUPABASE_URL") or "").strip(),
        "supabaseAnonKey": (os.environ.get("SUPABASE_ANON_KEY") or "").strip(),
    }


def _render_search_ui() -> str:
    path = _root / "templates" / "search.html"
    if not path.exists():
        return "<!DOCTYPE html><html><body><h1>Operators Vault</h1><p>Template not found.</p></body></html>"
    html = path.read_text(encoding="utf-8")
    cfg = _public_config()
    return (
        html.replace("{{ static_prefix }}", "/static")
        .replace("{{ api_base }}", cfg["apiBase"])
        .replace("{{ supabase_url }}", cfg["supabaseUrl"])
        .replace("{{ supabase_anon_key }}", cfg["supabaseAnonKey"])
        .replace("{{ request.url_for('search_ui') }}", "/search-ui")
    )
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

# ---------------------------------------------------------------------------
# In-memory job store with lifecycle management
# ---------------------------------------------------------------------------
# Each job: {status, type, result, error, logs, worker_id, started_at, updated_at}
_jobs: dict[str, dict] = {}
_speaker_columns_cache: dict[str, set] = {}
_jobs_lock = threading.Lock()
_worker_id = f"w-{uuid.uuid4().hex[:8]}"  # unique per container instance
_shutting_down = threading.Event()

# Stale job threshold: if a running job hasn't updated in this many seconds, mark failed
_STALE_JOB_TIMEOUT_SEC = int(os.environ.get("STALE_JOB_TIMEOUT_SEC", "900"))  # 15 min default
# Heartbeat interval for background jobs
_HEARTBEAT_INTERVAL_SEC = 30


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
    Upload CSVs into seed_links. Multipart form: 9operators, marketing_operator, finance_operators, titans, or operators_and_titans (single combined CSV; podcast inferred per row from title).
    Does not run backfill. Returns {ok, upserted}.
    """
    from youtube_client import load_all_seed_csvs
    form = await request.form()
    tmpdir = Path(tempfile.mkdtemp(prefix="seed_links_csv_"))
    paths: dict[str, str] = {}
    for key in ("9operators", "marketing_operator", "finance_operators", "titans", "operators_and_titans"):
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
        raise HTTPException(status_code=400, detail="Upload at least one CSV: 9operators, marketing_operator, finance_operators, titans, or operators_and_titans")
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


def _do_sync(job_id: str | None = None) -> dict:
    """Run fetch-new then process-new. Returns {ok, upserted, processed, video_ids}. Raises on env/error."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    if not os.environ.get("YOUTUBE_API_KEY"):
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY not set")

    # Pre-flight: validate Deepgram API key before downloading any audio
    try:
        check_api_key()
    except DeepgramAuthError as e:
        _log.error("Sync aborted: Deepgram API key invalid — %s", e)
        raise HTTPException(status_code=500, detail=f"Deepgram API key is invalid: {e}")

    import psycopg2
    _log.info("Sync starting: fetch-new phase")
    if job_id:
        _update_job_heartbeat(job_id, progress="fetching new videos")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    upserted = _fetch_new(cur)
    conn.commit()
    rows = _get_unprocessed(cur)
    cur.close()
    conn.close()
    _log.info("Sync: fetched %d new, %d unprocessed to process", upserted, len(rows))
    processed = []
    errors = []
    for i, (vid, pod) in enumerate(rows):
        if _shutting_down.is_set():
            _log.warning("Sync interrupted by shutdown after %d/%d videos", i, len(rows))
            errors.append("Interrupted by container shutdown")
            break
        if job_id:
            _update_job_heartbeat(job_id, progress=f"processing {i+1}/{len(rows)}: {vid}")
        try:
            ok = _process_one(vid, pod)
            if ok:
                processed.append(vid)
                _log.info("Processed video %s (%s) successfully", vid, pod)
            else:
                err_msg = f"{vid} ({pod}): Processing failed (check logs for details)"
                print(f"  [WARNING] Processing failed for {vid} ({pod})", flush=True)
                errors.append(err_msg)
                _log.warning("Processing failed for %s (%s)", vid, pod)
        except DeepgramAuthError as e:
            err_msg = f"FATAL: Deepgram API key invalid — aborting remaining {len(rows) - i - 1} videos. {e}"
            _log.error(err_msg)
            errors.append(err_msg)
            break
        except Exception as e:
            err_msg = f"{vid} ({pod}): {type(e).__name__}: {e!s}"
            _log.error("Processing exception for %s: %s", vid, err_msg)
            print(f"  [ERROR] Processing failed: {err_msg}", flush=True)
            import traceback
            print(f"  [ERROR] Traceback: {traceback.format_exc()}", flush=True)
            errors.append(err_msg)
    if errors:
        _log.warning("%d videos failed to process. First error: %s", len(errors), errors[0])

    # NOTE: We previously called _do_extract_insights_from_transcripts here as a
    # "safety net" to catch any videos that got transcribed but not insighted.
    # That call is redundant for the happy path: _process_one already extracts
    # insights inline (see pipeline.py step 5), and the backfill query filters
    # `WHERE video_id NOT IN (SELECT video_id FROM insights)` — so freshly
    # processed videos are filtered out. Calling it here only wastes a DB
    # round-trip in the common case and re-runs Claude only for partially-
    # processed historical videos (which should be repaired explicitly via
    # POST /extract-insights-backfill, not silently during cron sync).
    if processed:
        _log.info(
            "Sync: %d videos processed; insights extracted inline by _process_one",
            len(processed),
        )

    _log.info("Sync complete: upserted=%d processed=%d errors=%d", upserted, len(processed), len(errors))
    return {"ok": True, "upserted": upserted, "processed": len(processed), "video_ids": processed, "errors": errors[:5]}


def _do_process_new(job_id: str | None = None) -> dict:
    """Process all unprocessed videos in parallel. Returns {ok, processed, video_ids}. Raises on env/error."""
    import concurrent.futures
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")

    # Pre-flight: validate Deepgram API key before downloading any audio
    try:
        check_api_key()
    except DeepgramAuthError as e:
        _log.error("process-new aborted: Deepgram API key invalid — %s", e)
        raise HTTPException(status_code=500, detail=f"Deepgram API key is invalid: {e}")

    import psycopg2
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    rows = _get_unprocessed(cur)
    cur.close()
    conn.close()

    workers = int(os.environ.get("PROCESS_NEW_WORKERS", "4"))
    _log.info("process-new: %d unprocessed videos found, workers=%d", len(rows), workers)

    processed = []
    errors = []
    done_count = 0
    lock = threading.Lock()

    def _run_one(args):
        nonlocal done_count
        vid, pod = args
        if _shutting_down.is_set():
            return vid, False, "Interrupted by container shutdown"
        try:
            ok = _process_one(vid, pod)
            with lock:
                done_count += 1
                if job_id:
                    _update_job_heartbeat(job_id, progress=f"processed {done_count}/{len(rows)}: {vid}")
            if ok:
                _log.info("Processed video %s (%s) successfully", vid, pod)
                return vid, True, None
            else:
                _log.warning("Processing failed for %s (%s)", vid, pod)
                return vid, False, f"{vid} ({pod}): Processing failed"
        except DeepgramAuthError as e:
            return vid, False, f"FATAL:Deepgram:{e}"
        except Exception as e:
            _log.error("Processing exception for %s: %s", vid, e)
            return vid, False, f"{vid} ({pod}): {type(e).__name__}: {e!s}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for vid, ok, err in executor.map(_run_one, rows):
            if err and err.startswith("FATAL:Deepgram:"):
                errors.append(err)
                executor.shutdown(wait=False, cancel_futures=True)
                break
            if ok:
                processed.append(vid)
            elif err:
                errors.append(err)

    if errors:
        _log.warning("%d videos failed to process. First error: %s", len(errors), errors[0])
    _log.info("process-new complete: processed=%d errors=%d", len(processed), len(errors))
    return {"ok": True, "processed": len(processed), "video_ids": processed, "errors": errors[:5]}


@app.post("/fetch-new")
def fetch_new():
    """Fetch new videos from YouTube channels (9 Operators, Marketing, Finance) and upsert into videos. Requires DATABASE_URL and YOUTUBE_API_KEY."""
    return _do_fetch_new()


@app.post("/process-new")
def process_new():
    """Process all videos that have no transcription yet. Requires DATABASE_URL. Can be slow (audio download, transcribe, LLM per video)."""
    return _do_process_new()


def _do_extract_insights_from_transcripts(job_id: str | None = None, limit: int = 300) -> dict:
    """
    For every video that has a transcription but no insights, run insight extraction
    using the stored transcript (no re-download, no Deepgram). Much faster than process-new.
    """
    import concurrent.futures
    import psycopg2
    from insight_extractor import extract_insights, extract_timestamps, generate_title, make_framework

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT v.video_id, v.podcast, t.raw_text
        FROM videos v
        JOIN transcriptions t ON t.video_id = v.video_id
        WHERE v.video_id NOT IN (SELECT DISTINCT video_id FROM insights WHERE video_id IS NOT NULL)
        ORDER BY v.published_at DESC NULLS LAST
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    _log.info("extract-insights-backfill: %d videos need insight extraction", len(rows))
    if job_id:
        _update_job_heartbeat(job_id, progress=f"0/{len(rows)} videos queued")

    processed = []
    errors = []
    done_count = 0
    lock = threading.Lock()

    def _extract_one(args):
        nonlocal done_count
        video_id, podcast, raw_text = args
        if _shutting_down.is_set():
            return video_id, False, "shutdown"
        try:
            from company_extractor import extract_companies_from_text, link_insights_to_companies, link_video_to_companies
            from people_extractor import extract_people_from_segments, link_insights_to_people

            db = os.environ["DATABASE_URL"]
            conn2 = psycopg2.connect(db)
            cur2 = conn2.cursor()

            # Extract people from segments (already stored from prior transcription)
            speaker_to_id = extract_people_from_segments(cur2, video_id)

            # Chunk transcript and extract insights
            chunks = [raw_text[i:i+6000] for i in range(0, len(raw_text), 5500)]
            all_insights: list[dict] = []
            for ch in chunks:
                items = extract_insights(ch, prompt_set="operators")
                for it in items:
                    it["_chunk"] = ch
                    all_insights.append(it)

            # Clear old insights (safety) and insert new ones
            cur2.execute("DELETE FROM insights WHERE video_id = %s", (video_id,))

            # Load segments for timestamp lookup
            cur2.execute("SELECT start_time_sec, end_time_sec, text FROM segments s JOIN transcriptions t ON t.id = s.transcription_id WHERE t.video_id = %s ORDER BY start_time_sec", (video_id,))
            segs = cur2.fetchall()
            timestamped = "\n".join(f"[{r[0]:.1f}s] {r[2]}" for r in segs) if segs else raw_text

            insight_ids: list[str] = []
            for it in all_insights:
                cat = it.get("category") or ""
                title = (it.get("title") or "").strip()
                desc = (it.get("description") or "").strip()
                if len(title) < 3:
                    title = generate_title(desc or title, prompt_set="operators")
                elif len(title) > 120:
                    title = generate_title(desc or title, prompt_set="operators")
                start_sec, end_sec = extract_timestamps(timestamped, desc or title, prompt_set="operators")
                framework = make_framework(title or "Framework", it.get("_chunk", ""), prompt_set="operators") if ("ramework" in cat or cat == "Frameworks and exercises") else ""
                cur2.execute(
                    """INSERT INTO insights (video_id, podcast, category, title, description, start_time_sec, end_time_sec, framework_markdown)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (video_id, podcast, cat, title, desc, start_sec, end_sec, framework),
                )
                iid = cur2.fetchone()[0]
                insight_ids.append(str(iid))

            # Link people + companies
            link_insights_to_people(cur2, insight_ids, speaker_to_id)
            companies = extract_companies_from_text(raw_text)
            link_video_to_companies(cur2, video_id, companies)
            link_insights_to_companies(cur2, insight_ids, companies)

            conn2.commit()
            cur2.close()
            conn2.close()

            with lock:
                done_count += 1
                if job_id:
                    _update_job_heartbeat(job_id, progress=f"{done_count}/{len(rows)}: {video_id} ({len(insight_ids)} insights)")
            _log.info("extract-backfill ok: %s → %d insights", video_id, len(insight_ids))
            return video_id, True, None
        except Exception as e:
            _log.warning("extract-backfill error: %s — %s", video_id, e)
            return video_id, False, str(e)

    workers = int(os.environ.get("PROCESS_NEW_WORKERS", "4"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for video_id, ok, err in pool.map(_extract_one, rows):
            if ok:
                processed.append(video_id)
            else:
                errors.append({"video_id": video_id, "error": err})

    return {"ok": True, "processed": len(processed), "errors": len(errors), "video_ids": processed, "error_details": errors[:5]}


@app.post("/extract-insights-backfill")
def extract_insights_backfill(limit: int = 300):
    """
    Extract insights for all transcribed-but-no-insights videos without re-downloading audio.
    Much faster than /process-new. Safe to call multiple times (idempotent).
    """
    return _do_extract_insights_from_transcripts(limit=limit)


@app.post("/extract-insights-backfill/async")
def extract_insights_backfill_async(limit: int = 300):
    """Async wrapper for /extract-insights-backfill. Returns 202 with job_id immediately."""
    import uuid
    job_id = str(uuid.uuid4())
    _run_async_job(job_id, lambda: _do_extract_insights_from_transcripts(job_id=job_id, limit=limit), "extract-insights-backfill")
    return _async_202_response(job_id, "extract-insights-backfill")


@app.post("/run-migrate-phase1")
def run_migrate_phase1():
    """Run sql/migrate_phase1_youtube_titans.sql (add view_count, thumbnail_url, etc.). Safe to call multiple times."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    path = _root / "sql" / "migrate_phase1_youtube_titans.sql"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Migration file not found")
    sql = path.read_text(encoding="utf-8")
    import psycopg2
    statements = [
        s.strip() for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]
    # Only run DDL (e.g. ALTER TABLE); skip comment fragments that contained ";"
    statements = [s for s in statements if s.upper().startswith("ALTER TABLE")]
    results = []
    for stmt in statements:
        # Each DDL statement gets its own fresh connection to avoid pooler SSL drops
        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(stmt + ";" if not stmt.rstrip().endswith(";") else stmt)
            cur.close()
            conn.close()
            results.append({"stmt": stmt[:60], "ok": True})
        except Exception as e:
            results.append({"stmt": stmt[:60], "ok": False, "error": str(e)})
    failed = [r for r in results if not r["ok"]]
    if failed:
        raise HTTPException(status_code=500, detail=f"Migration failed: {failed}")
    return {"ok": True, "message": "Phase 1 migration applied.", "results": results}


@app.get("/health")
def health():
    """Check env, connectivity, jobs, and resource usage. Returns status, checks, active jobs, and memory info."""
    checks: dict[str, str] = {}
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        checks["database"] = "missing"
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.close()
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e!s}"

    # Check YouTube API key and library availability
    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    if not youtube_key:
        checks["youtube"] = "missing"
    else:
        try:
            from googleapiclient.discovery import build  # noqa: F401
            checks["youtube"] = "ok"
        except ImportError:
            checks["youtube"] = "error: google-api-python-client not installed"
    dg_key = os.environ.get("DEEPGRAM_API_KEY")
    if not dg_key:
        checks["deepgram"] = "missing"
    else:
        try:
            check_api_key(dg_key)
            checks["deepgram"] = "ok"
        except DeepgramAuthError:
            checks["deepgram"] = "error: invalid API key (401)"
        except Exception as e:
            checks["deepgram"] = f"error: {e!s}"
    checks["anthropic"] = "ok" if os.environ.get("ANTHROPIC_API_KEY") else "missing"
    checks["search"] = "ok"  # Using Postgres FTS as intended search backend

    # Job summary
    with _jobs_lock:
        running_count = sum(1 for j in _jobs.values() if j.get("status") == "running")
        total_jobs = len(_jobs)

    # Memory info (best-effort)
    memory_mb = None
    try:
        import resource
        # maxrss is in KB on Linux
        memory_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        pass

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": status,
        "checks": checks,
        "worker_id": _worker_id,
        "jobs_running": running_count,
        "jobs_total": total_jobs,
        "memory_mb": memory_mb,
        "shutting_down": _shutting_down.is_set(),
    }


def _search_postgres(
    q: str,
    podcast: str | None = None,
    category: str | None = None,
    video_id: str | None = None,
    person_id: str | None = None,
    company_id: str | None = None,
    is_panzerism: bool = False,
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
            where_clauses = ["fts @@ websearch_to_tsquery('english', %s)"]
            params: list = [q.strip()]
            if podcast:
                where_clauses.append("podcast = %s")
                params.append(podcast)
            if category:
                where_clauses.append("category ILIKE %s")
                params.append(f"%{category}%")
            if video_id:
                where_clauses.append("video_id = %s")
                params.append(video_id)
            params.append(limit)
            cur.execute(
                f"""
                SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec,
                       ts_rank(fts, websearch_to_tsquery('english', %s)) AS rank,
                       title AS headline_title,
                       ts_headline('english', description, websearch_to_tsquery('english', %s),
                           'MaxFragments=1,MaxWords=20,MinWords=5') AS headline_description
                FROM insights
                WHERE {" AND ".join(where_clauses)}
                ORDER BY rank DESC
                LIMIT %s
                """,
                [q.strip(), q.strip()] + params,
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
            seg_where = ["fts @@ websearch_to_tsquery('english', %s)"]
            seg_params: list = [q.strip()]
            if podcast:
                seg_where.append("podcast = %s")
                seg_params.append(podcast)
            if video_id:
                seg_where.append("video_id = %s")
                seg_params.append(video_id)
            seg_params.append(limit)
            cur.execute(
                f"""
                SELECT id, video_id, podcast, start_time_sec, end_time_sec, text, speaker_label,
                       ts_rank(fts, websearch_to_tsquery('english', %s)) AS rank,
                       ts_headline('english', text, websearch_to_tsquery('english', %s),
                           'MaxFragments=1,MaxWords=25,MinWords=10') AS headline
                FROM segments
                WHERE {" AND ".join(seg_where)}
                ORDER BY rank DESC
                LIMIT %s
                """,
                [q.strip(), q.strip()] + seg_params,
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
    # Phase 2: Filter by person_id or company_id (post-search filter)
    if person_id or company_id or is_panzerism:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        try:
            filtered_hits = []
            for h in hits:
                ins_id = h.get("id")
                if not ins_id:
                    continue
                # Check person filter
                if person_id:
                    cur.execute(
                        "SELECT 1 FROM insight_people WHERE insight_id = %s AND person_id = %s",
                        (ins_id, person_id),
                    )
                    if not cur.fetchone():
                        continue
                # Check company filter
                if company_id:
                    cur.execute(
                        "SELECT 1 FROM insight_companies WHERE insight_id = %s AND company_id = %s",
                        (ins_id, company_id),
                    )
                    if not cur.fetchone():
                        continue
                # Check Panzerisms (speaker = Jason Panzer)
                if is_panzerism:
                    # Find person_id for "Jason Panzer" or similar
                    cur.execute(
                        "SELECT id FROM people WHERE LOWER(name) LIKE %s",
                        ("%panzer%",),
                    )
                    panzer_id = cur.fetchone()
                    if panzer_id:
                        cur.execute(
                            "SELECT 1 FROM insight_people WHERE insight_id = %s AND person_id = %s",
                            (ins_id, str(panzer_id[0])),
                        )
                        if not cur.fetchone():
                            continue
                    else:
                        continue
                filtered_hits.append(h)
            hits = filtered_hits[:limit]
        finally:
            cur.close()
            conn.close()
    # Newsletter insights — included unless type_ is "moments" or explicit "insights" with no q
    if type_ in ("insights", "all", "newsletters") and q and q.strip():
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        try:
            q_clean = q.strip()
            nl_where = ["to_tsvector('english', coalesce(ni.title,'') || ' ' || coalesce(ni.description,'')) @@ websearch_to_tsquery('english', %s)"]
            nl_params: list = [q_clean, q_clean]  # first for WHERE tsquery, second for ts_rank
            if category:
                nl_where.append("ni.category ILIKE %s")
                nl_params.append(f"%{category}%")
            nl_params.append(limit)
            cur.execute(
                f"""
                SELECT ni.id, ni.source, ni.category, ni.title, ni.description,
                       n.subject, n.author, n.published_at,
                       ts_rank(to_tsvector('english', coalesce(ni.title,'') || ' ' || coalesce(ni.description,'')), websearch_to_tsquery('english', %s)) AS rank,
                       ni.newsletter_id::text
                FROM newsletter_insights ni
                JOIN newsletters n ON n.id = ni.newsletter_id
                WHERE {" AND ".join(nl_where)}
                ORDER BY rank DESC
                LIMIT %s
                """,
                nl_params,
            )
            for row in cur.fetchall():
                hits.append({
                    "type": "newsletter_insight",
                    "id": str(row[0]),
                    "source": row[1],
                    "category": row[2],
                    "title": row[3],
                    "description": row[4],
                    "subject": row[5],
                    "author": row[6],
                    "published_at": row[7].isoformat() if row[7] else None,
                    "rank": float(row[8]) if row[8] is not None else 0,
                    "headline_title": row[3],
                    "headline_description": row[4],
                    "newsletter_id": row[9],
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
    person_id: str | None = None,
    company_id: str | None = None,
    is_panzerism: bool = False,
    limit: int = 20,
    type_: str = "insights",
    _: dict = Depends(_verify_supabase_jwt),
):
    """Search insights and/or timestamp moments via Postgres FTS. Requires Bearer token (Supabase Auth). Params: q, podcast, category, video_id, person_id, company_id, is_panzerism, limit, type=insights|moments|all."""
    return _search_postgres(q, podcast=podcast, category=category, video_id=video_id, person_id=person_id, company_id=company_id, is_panzerism=is_panzerism, limit=limit, type_=type_)


def _list_episodes(podcast: str | None = None, limit: int = 100) -> dict:
    """List videos (episodes) with optional podcast filter. For catalog."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 500)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        if podcast:
            cur.execute(
                """
                SELECT video_id, title, podcast, duration_seconds, published_at, thumbnail_url, description
                FROM videos
                WHERE podcast = %s
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (podcast, limit),
            )
        else:
            cur.execute(
                """
                SELECT video_id, title, podcast, duration_seconds, published_at, thumbnail_url, description
                FROM videos
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
        episodes = [
            {
                "video_id": r[0],
                "title": r[1] or "",
                "podcast": r[2],
                "duration_seconds": r[3],
                "thumbnail_url": r[5],
                "description": r[6],
                "published_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        return {"episodes": episodes, "total": len(episodes)}
    finally:
        cur.close()
        conn.close()


def _list_people(limit: int = 200) -> dict:
    """List people for directory."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 500)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, role_or_title FROM people ORDER BY name LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        people_list = [
            {"id": str(r[0]), "name": r[1] or "", "role_or_title": r[2] or ""}
            for r in rows
        ]
        return {"people": people_list, "total": len(people_list)}
    finally:
        cur.close()
        conn.close()


def _list_insights(
    category: str | None = None,
    podcast: str | None = None,
    limit: int = 50,
) -> dict:
    """List insights with optional category/podcast filter (for Listen pages)."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 100)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        if category and podcast:
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec
                FROM insights
                WHERE category = %s AND podcast = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (category, podcast, limit),
            )
        elif category:
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec
                FROM insights
                WHERE category = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (category, limit),
            )
        elif podcast:
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec
                FROM insights
                WHERE podcast = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (podcast, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec, end_time_sec
                FROM insights
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
        hits = [
            {
                "type": "insight",
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "category": r[3],
                "title": r[4],
                "description": r[5],
                "start_time_sec": float(r[6]) if r[6] is not None else None,
                "end_time_sec": float(r[7]) if r[7] is not None else None,
                "headline_title": r[4],
                "headline_description": r[5],
            }
            for r in rows
        ]
        return {"category": category, "total": len(hits), "hits": hits}
    finally:
        cur.close()
        conn.close()


@app.get("/episodes")
def episodes(
    podcast: str | None = None,
    limit: int = 100,
):
    """List episodes (videos) for catalog. Optional podcast filter. Public — no auth required."""
    return _list_episodes(podcast=podcast, limit=limit)


@app.get("/people")
def people(
    limit: int = 200,
    _: dict = Depends(_verify_supabase_jwt),
):
    """List people for directory. Requires Bearer token."""
    return _list_people(limit=limit)


def _get_person_by_slug(slug: str) -> dict:
    """Get person by slug with episodes and insights."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, role_or_title, bio FROM people WHERE slug = %s", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Person not found")
        person_id, name, role, bio = row
        # Get episodes
        cur.execute(
            """
            SELECT DISTINCT v.video_id, v.title, v.podcast, v.published_at
            FROM videos v
            JOIN video_people vp ON vp.video_id = v.video_id
            WHERE vp.person_id = %s
            ORDER BY v.published_at DESC NULLS LAST
            LIMIT 50
            """,
            (person_id,),
        )
        episodes = [
            {
                "video_id": r[0],
                "title": r[1] or "",
                "podcast": r[2],
                "published_at": r[3].isoformat() if r[3] else None,
            }
            for r in cur.fetchall()
        ]
        # Get insights (quotes, frameworks)
        cur.execute(
            """
            SELECT i.id, i.video_id, i.podcast, i.category, i.title, i.description, i.start_time_sec
            FROM insights i
            JOIN insight_people ip ON ip.insight_id = i.id
            WHERE ip.person_id = %s
            ORDER BY i.created_at DESC
            LIMIT 50
            """,
            (person_id,),
        )
        insights = [
            {
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "category": r[3],
                "title": r[4],
                "description": r[5],
                "start_time_sec": float(r[6]) if r[6] is not None else None,
            }
            for r in cur.fetchall()
        ]
        return {
            "id": str(person_id),
            "name": name or "",
            "role_or_title": role or "",
            "bio": bio or "",
            "slug": slug,
            "episodes": episodes,
            "insights": insights,
        }
    finally:
        cur.close()
        conn.close()


def _get_company_by_slug(slug: str) -> dict:
    """Get company by slug with episodes and insights."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, type, description FROM companies WHERE slug = %s", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")
        company_id, name, comp_type, desc = row
        # Get episodes
        cur.execute(
            """
            SELECT DISTINCT v.video_id, v.title, v.podcast, v.published_at
            FROM videos v
            JOIN video_companies vc ON vc.video_id = v.video_id
            WHERE vc.company_id = %s
            ORDER BY v.published_at DESC NULLS LAST
            LIMIT 50
            """,
            (company_id,),
        )
        episodes = [
            {
                "video_id": r[0],
                "title": r[1] or "",
                "podcast": r[2],
                "published_at": r[3].isoformat() if r[3] else None,
            }
            for r in cur.fetchall()
        ]
        # Get insights
        cur.execute(
            """
            SELECT i.id, i.video_id, i.podcast, i.category, i.title, i.description, i.start_time_sec
            FROM insights i
            JOIN insight_companies ic ON ic.insight_id = i.id
            WHERE ic.company_id = %s
            ORDER BY i.created_at DESC
            LIMIT 50
            """,
            (company_id,),
        )
        insights = [
            {
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "category": r[3],
                "title": r[4],
                "description": r[5],
                "start_time_sec": float(r[6]) if r[6] is not None else None,
            }
            for r in cur.fetchall()
        ]
        return {
            "id": str(company_id),
            "name": name or "",
            "type": comp_type or "other",
            "description": desc or "",
            "slug": slug,
            "episodes": episodes,
            "insights": insights,
        }
    finally:
        cur.close()
        conn.close()


@app.get("/person/{slug}")
def person_detail(
    slug: str,
    _: dict = Depends(_verify_supabase_jwt),
):
    """Get person by slug with episodes and insights. Requires Bearer token."""
    return _get_person_by_slug(slug)


@app.get("/company/{slug}")
def company_detail(
    slug: str,
    _: dict = Depends(_verify_supabase_jwt),
):
    """Get company by slug with episodes and insights. Requires Bearer token."""
    return _get_company_by_slug(slug)


def _search_visuals(
    q: str,
    podcast: str | None = None,
    video_id: str | None = None,
    limit: int = 20,
) -> dict:
    """Search visual moments. Returns {query, total, hits}."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 100)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, video_id, podcast, start_time_sec, end_time_sec, description, transcript_excerpt, rank FROM search_visual_moments(%s, %s, 0, %s, %s)",
            (q.strip() if q else "", limit, podcast, video_id),
        )
        hits = [
            {
                "type": "visual",
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "start_time_sec": float(r[3]) if r[3] is not None else None,
                "end_time_sec": float(r[4]) if r[4] is not None else None,
                "description": r[5],
                "transcript_excerpt": r[6],
                "rank": float(r[7]) if r[7] is not None else 0,
            }
            for r in cur.fetchall()
        ]
        return {"query": q or "(all)", "total": len(hits), "hits": hits}
    finally:
        cur.close()
        conn.close()


@app.get("/visuals")
def visuals_search(
    q: str = "",
    podcast: str | None = None,
    video_id: str | None = None,
    limit: int = 20,
    _: dict = Depends(_verify_supabase_jwt),
):
    """Search visual moments (screen-shares, slides). Requires Bearer token."""
    return _search_visuals(q, podcast=podcast, video_id=video_id, limit=limit)


def _get_related_content(video_id: str, insight_id: str | None = None, limit: int = 5) -> dict:
    """Get related insights from the same video or similar videos."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        if insight_id:
            # Get related from same video, excluding this insight
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec
                FROM insights
                WHERE video_id = (SELECT video_id FROM insights WHERE id = %s)
                  AND id != %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (insight_id, insight_id, limit),
            )
        else:
            # Get related from same video
            cur.execute(
                """
                SELECT id, video_id, podcast, category, title, description, start_time_sec
                FROM insights
                WHERE video_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (video_id, limit),
            )
        hits = [
            {
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "category": r[3],
                "title": r[4],
                "description": r[5],
                "start_time_sec": float(r[6]) if r[6] is not None else None,
            }
            for r in cur.fetchall()
        ]
        return {"related": hits, "total": len(hits)}
    finally:
        cur.close()
        conn.close()


@app.get("/related")
def related_content(
    video_id: str | None = None,
    insight_id: str | None = None,
    limit: int = 5,
    _: dict = Depends(_verify_supabase_jwt),
):
    """Get related insights (same video or similar). Requires Bearer token."""
    if not video_id and not insight_id:
        raise HTTPException(status_code=400, detail="video_id or insight_id required")
    return _get_related_content(video_id or "", insight_id, limit=limit)


@app.get("/insights")
def insights_list(
    category: str | None = None,
    podcast: str | None = None,
    limit: int = 50,
    _: dict = Depends(_verify_supabase_jwt),
):
    """List insights by category/podcast (for Listen pages). Requires Bearer token."""
    return _list_insights(category=category, podcast=podcast, limit=limit)


# ---------------------------------------------------------------------------
# Speaker Profiles (public — no JWT required)
# ---------------------------------------------------------------------------

class SpeakerUpsertRequest(BaseModel):
    slug: str
    name: str
    bio: str | None = None
    twitter_handle: str | None = None
    photo_url: str | None = None
    company: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    website: str | None = None
    source: str = "manual"
    is_host: bool = False
    host_podcast: str | None = None


def _list_speakers(limit: int = 50, offset: int = 0) -> dict:
    """List all speaker profiles."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    limit = min(limit, 200)
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        # Check which host columns exist (avoids DDL permission issues); use cache to skip repeated queries
        if "speaker_profiles" in _speaker_columns_cache:
            existing_cols = _speaker_columns_cache["speaker_profiles"]
        else:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'speaker_profiles' AND column_name IN ('is_host', 'host_podcast')
            """)
            existing_cols = {r[0] for r in cur.fetchall()}
            _speaker_columns_cache["speaker_profiles"] = existing_cols
        has_host_cols = "is_host" in existing_cols and "host_podcast" in existing_cols

        # Try to add missing columns if needed
        if not has_host_cols:
            conn.rollback()
            try:
                conn.autocommit = True
                if "is_host" not in existing_cols:
                    cur.execute("ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS is_host BOOLEAN DEFAULT FALSE")
                if "host_podcast" not in existing_cols:
                    cur.execute("ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS host_podcast TEXT")
                has_host_cols = True
                # Invalidate cache so next call re-fetches the updated columns
                _speaker_columns_cache.pop("speaker_profiles", None)
            except Exception as e:
                _log.warning("add_host_cols_failed", extra={"error": str(e)})
            finally:
                conn.autocommit = False

        if has_host_cols:
            cur.execute(
                """
                SELECT sp.id, sp.slug, sp.name, sp.bio, sp.twitter_handle, sp.linkedin_url,
                       sp.photo_url, sp.company, sp.title, sp.website, sp.source,
                       sp.created_at, sp.updated_at,
                       COUNT(DISTINCT ip.insight_id) AS insight_count,
                       COALESCE(sp.is_host, FALSE) AS is_host,
                       sp.host_podcast
                FROM speaker_profiles sp
                LEFT JOIN people p ON LOWER(p.name) = LOWER(sp.name) OR p.slug = sp.slug
                LEFT JOIN insight_people ip ON ip.person_id = p.id
                GROUP BY sp.id, sp.slug, sp.name, sp.bio, sp.twitter_handle, sp.linkedin_url,
                         sp.photo_url, sp.company, sp.title, sp.website, sp.source,
                         sp.created_at, sp.updated_at, sp.is_host, sp.host_podcast
                ORDER BY COALESCE(sp.is_host, FALSE) DESC, insight_count DESC, sp.name
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
        else:
            # Fallback: columns don't exist yet, query without them
            cur.execute(
                """
                SELECT sp.id, sp.slug, sp.name, sp.bio, sp.twitter_handle, sp.linkedin_url,
                       sp.photo_url, sp.company, sp.title, sp.website, sp.source,
                       sp.created_at, sp.updated_at,
                       COUNT(DISTINCT ip.insight_id) AS insight_count
                FROM speaker_profiles sp
                LEFT JOIN people p ON LOWER(p.name) = LOWER(sp.name) OR p.slug = sp.slug
                LEFT JOIN insight_people ip ON ip.person_id = p.id
                GROUP BY sp.id, sp.slug, sp.name, sp.bio, sp.twitter_handle, sp.linkedin_url,
                         sp.photo_url, sp.company, sp.title, sp.website, sp.source,
                         sp.created_at, sp.updated_at
                ORDER BY insight_count DESC, sp.name
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM speaker_profiles")
        total = cur.fetchone()[0]
        speakers = [
            {
                "id": str(r[0]),
                "slug": r[1],
                "name": r[2],
                "bio": r[3],
                "twitter_handle": r[4],
                "linkedin_url": r[5],
                "photo_url": r[6],
                "company": r[7],
                "title": r[8],
                "website": r[9],
                "source": r[10],
                "created_at": r[11].isoformat() if r[11] else None,
                "updated_at": r[12].isoformat() if r[12] else None,
                "insight_count": int(r[13]),
                "is_host": bool(r[14]) if has_host_cols else False,
                "host_podcast": r[15] if has_host_cols else None,
            }
            for r in rows
        ]
        return {"speakers": speakers, "total": total, "limit": limit, "offset": offset}
    finally:
        cur.close()
        conn.close()


def _get_speaker_by_slug(slug: str) -> dict:
    """Get a speaker profile with their top insights."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        # Check which host columns exist
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'speaker_profiles' AND column_name IN ('is_host', 'host_podcast')
        """)
        existing_cols = {r[0] for r in cur.fetchall()}
        has_host_cols = "is_host" in existing_cols and "host_podcast" in existing_cols

        if has_host_cols:
            cur.execute(
                """
                SELECT id, slug, name, bio, twitter_handle, linkedin_url, photo_url,
                       company, title, website, source, created_at, updated_at,
                       COALESCE(is_host, FALSE), host_podcast
                FROM speaker_profiles
                WHERE slug = %s
                """,
                (slug,),
            )
        else:
            cur.execute(
                """
                SELECT id, slug, name, bio, twitter_handle, linkedin_url, photo_url,
                       company, title, website, source, created_at, updated_at
                FROM speaker_profiles
                WHERE slug = %s
                """,
                (slug,),
            )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Speaker not found")
        speaker = {
            "id": str(row[0]),
            "slug": row[1],
            "name": row[2],
            "bio": row[3],
            "twitter_handle": row[4],
            "linkedin_url": row[5],
            "photo_url": row[6],
            "company": row[7],
            "title": row[8],
            "website": row[9],
            "source": row[10],
            "created_at": row[11].isoformat() if row[11] else None,
            "updated_at": row[12].isoformat() if row[12] else None,
            "is_host": bool(row[13]) if has_host_cols else False,
            "host_podcast": row[14] if has_host_cols else None,
        }
        speaker_name = row[2]  # e.g. "Roman Khan"

        # Primary: explicit insight_people join
        cur.execute(
            """
            SELECT i.id, i.video_id, i.podcast, i.category, i.title, i.description, i.start_time_sec
            FROM insights i
            JOIN insight_people ip ON ip.insight_id = i.id
            JOIN people p ON p.id = ip.person_id
            WHERE (p.slug = %s OR LOWER(p.name) = LOWER(%s))
            ORDER BY i.created_at DESC
            LIMIT 30
            """,
            (slug, speaker_name),
        )
        insights = [
            {
                "id": str(r[0]),
                "video_id": r[1],
                "podcast": r[2],
                "category": r[3],
                "title": r[4],
                "description": r[5],
                "start_time_sec": float(r[6]) if r[6] is not None else None,
            }
            for r in cur.fetchall()
        ]

        # Fallback: FTS search for the speaker's name in insight title/description
        # Handles cases where insight_people wasn't populated (most batch-extracted insights)
        if not insights:
            # Also search segments (podcast transcripts) for the speaker name
            name_query = speaker_name.replace(" ", " & ")  # "Roman & Khan"
            # Derive first/last name for noise filtering
            name_parts = speaker_name.strip().split()
            speaker_first = name_parts[0].lower() if name_parts else ""
            speaker_last = name_parts[-1].lower() if len(name_parts) > 1 else ""

            def _is_noisy_via_mention(title: str, spk_first: str, spk_last: str) -> bool:
                """Return True if this insight title is a noisy attribution, not a real insight BY the speaker."""
                t = title or ""
                t_lower = t.lower()
                # Exclude "X (via SpeakerName)" style titles
                if " (via " in t:
                    return True
                # Exclude "(as cited by SpeakerName)" style titles
                if "(as cited by " in t_lower:
                    return True
                # Exclude titles that start with "Host " (host intro labels like "Host (introducing Roman Khan)")
                if t_lower.startswith("host ") or t_lower.startswith("host("):
                    return True
                # Exclude titles that look like "Person Name (to/via/re: SpeakerName)" where
                # the speaker name doesn't appear in the part before the parenthesis
                if "(" in t:
                    before_paren = t[:t.index("(")].strip().lower()
                    # If the part before the paren has words (looks like a name) and
                    # neither the speaker's first nor last name appears in it, it's likely
                    # someone else's name with an attribution note
                    if before_paren and spk_first and spk_last:
                        if spk_first not in before_paren and spk_last not in before_paren:
                            # Additional guard: the part after ( should contain attribution language
                            after_paren = t_lower[t_lower.index("("):]
                            if any(kw in after_paren for kw in ("via ", "as cited", "quoting", "per ", "citing", " to ", "re: ", "(to ", "(re ")):
                                return True
                return False

            cur.execute(
                """
                SELECT DISTINCT ON (i.id) i.id, i.video_id, i.podcast, i.category, i.title, i.description, i.start_time_sec
                FROM insights i
                WHERE fts @@ to_tsquery('english', %s)
                ORDER BY i.id, i.created_at DESC
                LIMIT 50
                """,
                (name_query,),
            )
            insights = [
                {
                    "id": str(r[0]),
                    "video_id": r[1],
                    "podcast": r[2],
                    "category": r[3],
                    "title": r[4],
                    "description": r[5],
                    "start_time_sec": float(r[6]) if r[6] is not None else None,
                    "via_mention": True,
                }
                for r in cur.fetchall()
                if not _is_noisy_via_mention(r[4], speaker_first, speaker_last)
            ][:30]

            # If still none, try searching the segments table for transcript mentions
            # and surface the insights from those episodes
            if not insights:
                cur.execute(
                    """
                    SELECT DISTINCT i.id, i.video_id, i.podcast, i.category, i.title, i.description, i.start_time_sec
                    FROM segments s
                    JOIN transcriptions t ON t.id = s.transcription_id
                    JOIN insights i ON i.video_id = t.video_id
                    WHERE s.fts @@ to_tsquery('english', %s)
                    ORDER BY i.id
                    LIMIT 50
                    """,
                    (name_query,),
                )
                insights = [
                    {
                        "id": str(r[0]),
                        "video_id": r[1],
                        "podcast": r[2],
                        "category": r[3],
                        "title": r[4],
                        "description": r[5],
                        "start_time_sec": float(r[6]) if r[6] is not None else None,
                        "via_mention": True,
                    }
                    for r in cur.fetchall()
                    if not _is_noisy_via_mention(r[4], speaker_first, speaker_last)
                ][:30]

            # Tier 4: Search newsletter_insights for mentions of the speaker's name
            newsletter_insights = []
            try:
                cur.execute(
                    """
                    SELECT ni.id, ni.newsletter_id, ni.source, ni.category, ni.title, ni.description,
                           n.subject, n.author, n.published_at
                    FROM newsletter_insights ni
                    JOIN newsletters n ON n.id = ni.newsletter_id
                    WHERE ni.fts @@ to_tsquery('english', %s)
                    ORDER BY ni.id
                    LIMIT 50
                    """,
                    (name_query,),
                )
                newsletter_insights = [
                    {
                        "id": "ni_" + str(r[0]),
                        "newsletter_id": str(r[1]),
                        "source": r[2],
                        "category": r[3],
                        "title": r[4],
                        "description": r[5],
                        "subject": r[6],
                        "author": r[7],
                        "published_at": r[8].isoformat() if r[8] else None,
                        "via_mention": True,
                        "type": "newsletter",
                    }
                    for r in cur.fetchall()
                    if not _is_noisy_via_mention(r[4], speaker_first, speaker_last)
                ][:30]
            except Exception:
                # newsletter_insights table or fts column may not exist — skip gracefully
                conn.rollback()

            # Merge and deduplicate by id
            seen_ids = {i["id"] for i in insights}
            for ni in newsletter_insights:
                if ni["id"] not in seen_ids:
                    insights.append(ni)
                    seen_ids.add(ni["id"])

        speaker["insights"] = insights
        speaker["insights_via_mention"] = any(i.get("via_mention") for i in insights)
        return speaker
    finally:
        cur.close()
        conn.close()


def _upsert_speaker(data: SpeakerUpsertRequest) -> dict:
    """Upsert a speaker profile."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    cur = conn.cursor()
    try:
        # Check which host columns exist
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'speaker_profiles' AND column_name IN ('is_host', 'host_podcast')
        """)
        existing_cols = {r[0] for r in cur.fetchall()}
        has_host_cols = "is_host" in existing_cols and "host_podcast" in existing_cols

        # Try to add missing columns if needed
        if not has_host_cols:
            conn.rollback()
            try:
                conn.autocommit = True
                if "is_host" not in existing_cols:
                    cur.execute("ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS is_host BOOLEAN DEFAULT FALSE")
                if "host_podcast" not in existing_cols:
                    cur.execute("ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS host_podcast TEXT")
                has_host_cols = True
            except Exception as e:
                _log.warning("add_host_cols_failed_upsert", extra={"error": str(e)})
            finally:
                conn.autocommit = False

        if has_host_cols:
            cur.execute(
                """
                INSERT INTO speaker_profiles
                    (slug, name, bio, twitter_handle, linkedin_url, photo_url, company, title, website, source, is_host, host_podcast)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    bio = COALESCE(EXCLUDED.bio, speaker_profiles.bio),
                    twitter_handle = COALESCE(EXCLUDED.twitter_handle, speaker_profiles.twitter_handle),
                    linkedin_url = COALESCE(EXCLUDED.linkedin_url, speaker_profiles.linkedin_url),
                    photo_url = COALESCE(EXCLUDED.photo_url, speaker_profiles.photo_url),
                    company = COALESCE(EXCLUDED.company, speaker_profiles.company),
                    title = COALESCE(EXCLUDED.title, speaker_profiles.title),
                    website = COALESCE(EXCLUDED.website, speaker_profiles.website),
                    source = EXCLUDED.source,
                    is_host = EXCLUDED.is_host,
                    host_podcast = COALESCE(EXCLUDED.host_podcast, speaker_profiles.host_podcast),
                    updated_at = NOW()
                RETURNING id, slug, name, source, updated_at
                """,
                (
                    data.slug, data.name, data.bio, data.twitter_handle, data.linkedin_url,
                    data.photo_url, data.company, data.title, data.website, data.source,
                    data.is_host, data.host_podcast,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO speaker_profiles
                    (slug, name, bio, twitter_handle, linkedin_url, photo_url, company, title, website, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    bio = COALESCE(EXCLUDED.bio, speaker_profiles.bio),
                    twitter_handle = COALESCE(EXCLUDED.twitter_handle, speaker_profiles.twitter_handle),
                    linkedin_url = COALESCE(EXCLUDED.linkedin_url, speaker_profiles.linkedin_url),
                    photo_url = COALESCE(EXCLUDED.photo_url, speaker_profiles.photo_url),
                    company = COALESCE(EXCLUDED.company, speaker_profiles.company),
                    title = COALESCE(EXCLUDED.title, speaker_profiles.title),
                    website = COALESCE(EXCLUDED.website, speaker_profiles.website),
                    source = EXCLUDED.source,
                    updated_at = NOW()
                RETURNING id, slug, name, source, updated_at
                """,
                (
                    data.slug, data.name, data.bio, data.twitter_handle, data.linkedin_url,
                    data.photo_url, data.company, data.title, data.website, data.source,
                ),
            )
        row = cur.fetchone()
        conn.commit()
        return {
            "ok": True,
            "id": str(row[0]),
            "slug": row[1],
            "name": row[2],
            "source": row[3],
            "updated_at": row[4].isoformat() if row[4] else None,
        }
    finally:
        cur.close()
        conn.close()


@app.get("/speakers")
def speakers_list(limit: int = 50, offset: int = 0):
    """List all speaker profiles. Public — no auth required. Params: limit (max 200), offset."""
    return _list_speakers(limit=limit, offset=offset)


@app.get("/speakers/{slug}")
def speaker_detail(slug: str):
    """Get a single speaker profile with their top insights. Public — no auth required."""
    return _get_speaker_by_slug(slug)


@app.post("/speakers")
def speaker_upsert(body: SpeakerUpsertRequest):
    """Upsert a speaker profile. Public — no auth required. Body: {slug, name, bio?, twitter_handle?, photo_url?, company?, title?}."""
    return _upsert_speaker(body)


@app.post("/admin/migrate-host-fields")
def admin_migrate_host_fields():
    """Run the is_host/host_podcast migration directly. No auth required (idempotent DDL)."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    results = []
    conn = psycopg2.connect(db_url, connect_timeout=10)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in [
            "ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS is_host BOOLEAN DEFAULT FALSE",
            "ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS host_podcast TEXT",
            "CREATE INDEX IF NOT EXISTS idx_speaker_profiles_is_host ON speaker_profiles(is_host) WHERE is_host = TRUE",
        ]:
            try:
                cur.execute(stmt)
                results.append({"stmt": stmt[:60], "ok": True})
            except Exception as e:
                results.append({"stmt": stmt[:60], "ok": False, "error": str(e)})
        cur.close()
    finally:
        conn.close()
    return {"results": results}


# ---------------------------------------------------------------------------

class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    context_limit: int = 20
    history: list[ChatHistoryMessage] = []


@app.post("/chat")
def chat(
    body: ChatRequest,
    _: dict = Depends(_verify_supabase_jwt),
):
    """Ask the vault: search newsletter + podcast excerpts, then LLM reply with operator-grade context."""
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message required")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")

    # Extract keywords from conversational questions before FTS search.
    # plainto/websearch_to_tsquery require ALL terms to match; a conversational
    # question like "How do 8-figure brands approach BFCM prep?" returns 0 hits
    # because stop words + rare terms dilute the AND-query. We strip noise words
    # and try the full question first, then fall back to keyword-only query.
    _STOP = frozenset(["how", "do", "does", "what", "why", "when", "where", "who",
                       "can", "should", "would", "could", "are", "is", "the", "a",
                       "an", "to", "for", "of", "in", "on", "at", "about", "with",
                       "and", "or", "but", "not", "if", "then", "i", "we", "you",
                       "they", "my", "your", "their", "say", "says", "approach",
                       "tell", "think", "use", "some", "most", "more", "best",
                       "good", "get", "into", "from", "by"])

    def _extract_keywords(q: str) -> str:
        import re as _re
        # Strip punctuation (keep letters/digits/spaces), lowercase, split
        words = _re.sub(r"[^\w\s]", " ", q.lower()).split()
        # Remove stop words, short words, and tokens containing digits (e.g. "8")
        kw = [w for w in words if w not in _STOP and len(w) > 2 and not any(c.isdigit() for c in w)]
        return " OR ".join(kw[:6])  # OR-joined for maximum recall in fallback

    # Search both podcast insights and newsletter insights
    search_result = _search_postgres(msg, limit=body.context_limit, type_="all")
    hits = search_result.get("hits") or []

    # If no hits with full question, retry with OR-joined extracted keywords
    # This handles conversational phrasing and acronyms like BFCM that need
    # broader matching rather than strict AND across all terms.
    if not hits:
        kw_query = _extract_keywords(msg)
        if kw_query and kw_query.replace(" OR ", " ").strip() != msg.lower().strip():
            search_result = _search_postgres(kw_query, limit=body.context_limit, type_="all")
            hits = search_result.get("hits") or []

    # Enrich podcast insights with speaker names via people join
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        insight_ids = [h["id"] for h in hits if h.get("type") != "newsletter_insight" and h.get("id")]
        if insight_ids:
            cur.execute(
                """
                SELECT ip.insight_id::text, STRING_AGG(p.name, ', ') as speakers
                FROM insight_people ip JOIN people p ON p.id = ip.person_id
                WHERE ip.insight_id::text = ANY(%s)
                GROUP BY ip.insight_id
                """,
                (insight_ids,),
            )
            speaker_map = {row[0]: row[1] for row in cur.fetchall()}
            for h in hits:
                if h.get("id") in speaker_map:
                    h["speaker_name"] = speaker_map[h["id"]]
        cur.close()
        conn.close()
    except Exception:
        pass

    # Sort by rank descending, take top N
    hits = sorted(hits, key=lambda h: float(h.get("rank") or 0), reverse=True)[: body.context_limit]

    context_parts = []
    for h in hits:
        h_type = h.get("type", "")
        if h_type == "newsletter_insight":
            author = h.get("author") or h.get("source") or "Newsletter"
            title = h.get("headline_title") or h.get("title") or ""
            desc = h.get("headline_description") or h.get("description") or ""
            text = f"{title}. {desc}" if desc else title
            context_parts.append(f"[Newsletter — {author}] {text[:600]}")
        else:
            pod = (h.get("podcast") or "").replace("_", " ").title()
            speaker = h.get("speaker_name") or h.get("speaker") or ""
            start = h.get("start_time_sec")
            t = h.get("headline_title") or h.get("headline_description") or h.get("headline") or h.get("text") or ""
            if not pod:
                pod = "Operators Podcast"
            label = f"{pod}" + (f" — {speaker}" if speaker else "") + (f" @ {int(start)}s" if start is not None else "")
            context_parts.append(f"[{label}] {t[:600]}")

    context = "\n\n".join(context_parts) if context_parts else "No matching excerpts found in the vault for this query."

    system = """You are the ECOM Operators Vault AI — a specialized assistant trained on hundreds of hours of content from the world's best 7-, 8-, and 9-figure DTC operators.

Your knowledge base includes:
- Podcast insights from 9 Operators, Marketing Operators, Finance Operators, and TITANS — featuring the top ecommerce operators in the world
- Newsletters from Nik Sharma, Taylor Holiday (CTC/Common Thread Collective), Matt Bertulli, Chase Dimond, and the Operators Newsletter

Your role is to give direct, operator-grade, actionable answers — not generic marketing advice. You think in real business terms:
- True profitability metrics: MER (Marketing Efficiency Ratio), nCAC (new Customer Acquisition Cost), LTV:nCAC ratio, Contribution Margin, Net Profit, Payback Period — NOT just ROAS or CPM
- Real growth frameworks that 8-figure operators actually use
- Specific, named strategies with context on who uses them and why

When answering:
1. Lead with the direct answer or framework — be specific, not vague
2. Cite operators by name and source: e.g. "Taylor Holiday at CTC has talked about..." or "From Nik Sharma's newsletter..."
3. Give frameworks with concrete steps or numbers when the context supports it
4. Explain the "why" — operators don't just follow tactics, they understand first principles
5. If the question is about metrics, always explain why operators prefer certain metrics over vanity metrics like ROAS
6. Be direct and confident — channel the voice of operators who've seen what works at scale

Use the provided vault excerpts as your primary source. When excerpts are relevant, synthesize them into a cohesive answer rather than just listing quotes. If the vault doesn't have specific coverage, say so briefly and share your best operator-level thinking on the topic."""

    # Build conversation history for the prompt
    history_text = ""
    if body.history:
        history_lines = []
        for turn in body.history[-6:]:  # last 6 turns for context
            role = "User" if turn.role == "user" else "Assistant"
            history_lines.append(f"{role}: {turn.content}")
        if history_lines:
            history_text = "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

    user_content = f"{history_text}Vault excerpts relevant to this question:\n\n{context}\n\nQuestion: {msg}"

    agent_key = os.environ.get("AGENT_SERVER_API_KEY", "")
    try:
        headers = {"Content-Type": "application/json"}
        if agent_key:
            headers["Authorization"] = f"Bearer {agent_key}"
        full_prompt = f"System: {system}\n\n{user_content}"
        agent_res = requests.post(
            "https://ent-agent-server-production.up.railway.app/complete",
            json={"prompt": full_prompt, "max_tokens": 1500},
            headers=headers,
            timeout=90,
        )
        agent_res.raise_for_status()
        data = agent_res.json()
        reply = data.get("text") or data.get("completion") or data.get("content") or ""
        sources = []
        seen_ids = set()
        for h in hits[:8]:
            hid = str(h.get("id") or "")
            if hid in seen_ids:
                continue
            seen_ids.add(hid)
            h_type = h.get("type", "")
            if h_type == "newsletter_insight":
                sources.append({
                    "id": hid,
                    "title": h.get("title") or h.get("headline_title") or "",
                    "description": h.get("description") or h.get("headline_description") or "",
                    "source": "Newsletter",
                    "author": h.get("author") or h.get("source") or "",
                    "category": h.get("category"),
                })
            else:
                sources.append({
                    "id": hid,
                    "title": h.get("headline_title") or h.get("title") or "",
                    "description": h.get("headline_description") or h.get("description") or "",
                    "source": (h.get("podcast") or "").replace("_", " ").title(),
                    "author": h.get("speaker_name") or h.get("speaker") or "",
                    "podcast": h.get("podcast"),
                    "category": h.get("category"),
                })
        return {"reply": reply, "citations": len(hits), "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e!s}")


@app.get("/config")
def config():
    """Public config for frontends (API base URL, Supabase URL + anon key). Set in Railway/Vercel env."""
    return _public_config()


def _render_episodes_ui() -> str:
    path = _root / "templates" / "episodes.html"
    if not path.exists():
        return "<!DOCTYPE html><html><body><h1>Operators Vault</h1><p>Episodes template not found.</p></body></html>"
    html = path.read_text(encoding="utf-8")
    cfg = _public_config()
    return (
        html.replace("{{ static_prefix }}", "/static")
        .replace("{{ api_base }}", cfg["apiBase"])
        .replace("{{ supabase_url }}", cfg["supabaseUrl"])
        .replace("{{ supabase_anon_key }}", cfg["supabaseAnonKey"])
    )


@app.get("/search-ui", response_class=HTMLResponse)
def search_ui():
    """Search UI: sign in (token), filters, and result cards. Uses templates/search.html and static assets."""
    return _render_search_ui()


@app.get("/episodes-ui", response_class=HTMLResponse)
def episodes_ui():
    """Episodes catalog: list videos by show. Same auth as search."""
    return _render_episodes_ui()


def _render_template(name: str) -> str:
    """Render a template with public config. Name = filename without .html."""
    path = _root / "templates" / f"{name}.html"
    if not path.exists():
        return f"<!DOCTYPE html><html><body><h1>Operators Vault</h1><p>Template {name} not found.</p></body></html>"
    html = path.read_text(encoding="utf-8")
    cfg = _public_config()
    return (
        html.replace("{{ static_prefix }}", "/static")
        .replace("{{ api_base }}", cfg["apiBase"])
        .replace("{{ supabase_url }}", cfg["supabaseUrl"])
        .replace("{{ supabase_anon_key }}", cfg["supabaseAnonKey"])
    )


@app.get("/people-ui", response_class=HTMLResponse)
def people_ui():
    """People directory. Same auth as search."""
    return _render_template("people")


@app.get("/insights-ui", response_class=HTMLResponse)
def insights_ui():
    """Listen: insights by type (query param type=quote|frameworks|...). Same auth as search."""
    return _render_template("insights")


@app.get("/ask-ui", response_class=HTMLResponse)
def ask_ui():
    """Ask: chat over the vault. Same auth as search."""
    return _render_template("ask")


@app.get("/person-ui/{slug}", response_class=HTMLResponse)
def person_ui(slug: str):
    """Person detail page. Same auth as search."""
    return _render_template("person")


@app.get("/company-ui/{slug}", response_class=HTMLResponse)
def company_ui(slug: str):
    """Company detail page. Same auth as search."""
    return _render_template("company")


@app.post("/sync")
def sync():
    """Run fetch-new then process-new in one call. Good for cron/n8n. Can be slow. For 202 + job, use POST /sync/async."""
    return _do_sync()


def _update_job_heartbeat(job_id: str, **extra: object) -> None:
    """Update heartbeat timestamp and optional extra fields for a running job."""
    with _jobs_lock:
        j = _jobs.get(job_id)
        if j and j["status"] == "running":
            j["updated_at"] = time.time()
            for k, v in extra.items():
                j[k] = v


def _notify_slack(message: str) -> None:
    """Fire-and-forget Slack alert via chat.postMessage. Silently ignores all errors."""
    try:
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        channel = os.environ.get("SLACK_ALERT_CHANNEL", "#general")
        if not token:
            return
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": message},
            timeout=5,
        )
    except Exception:
        pass


def _run_async_job(job_id: str, fn, job_type: str):
    """Run fn() in a background thread with heartbeat, structured logging, and captured output."""
    now = time.time()
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "type": job_type,
            "result": None,
            "error": None,
            "logs": None,
            "worker_id": _worker_id,
            "started_at": now,
            "updated_at": now,
        }
    log_job_event(job_id, "started", {"type": job_type, "worker_id": _worker_id})

    # Heartbeat thread keeps updated_at fresh so stale detection works
    heartbeat_stop = threading.Event()

    def heartbeat():
        while not heartbeat_stop.wait(_HEARTBEAT_INTERVAL_SEC):
            _update_job_heartbeat(job_id)
            log_job_event(job_id, "heartbeat", {"type": job_type})

    def run():
        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()
        buf_out = io.StringIO()
        buf_err = io.StringIO()

        # Per-thread log capture: attach a StreamHandler to the root logger
        # that ONLY accepts records emitted on this worker thread. This is
        # necessary because structured_logger.py binds StreamHandler(sys.stderr)
        # at import time, so contextlib.redirect_stderr cannot intercept it.
        # We filter on thread name to keep concurrent jobs isolated.
        thread_name = threading.current_thread().name
        log_buf = io.StringIO()
        log_handler = logging.StreamHandler(log_buf)
        try:
            from structured_logger import JSONFormatter
            log_handler.setFormatter(JSONFormatter())
        except Exception:
            log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

        class _ThreadFilter(logging.Filter):
            def __init__(self, name: str):
                super().__init__()
                self._target = name
            def filter(self, record: logging.LogRecord) -> bool:
                return record.threadName == self._target

        log_handler.addFilter(_ThreadFilter(thread_name))
        log_handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)

        def _drain_logs() -> str:
            try:
                return log_buf.getvalue()[-16000:]
            except Exception:
                return ""

        try:
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                out = fn()
            captured_logs = _drain_logs()
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = out
                _jobs[job_id]["updated_at"] = time.time()
                _jobs[job_id]["logs"] = {
                    "stdout": buf_out.getvalue()[-8000:],
                    "stderr": buf_err.getvalue()[-8000:],
                    "captured": captured_logs,
                }
            log_job_event(job_id, "completed", {"type": job_type, "result_keys": list((out or {}).keys()) if isinstance(out, dict) else None})

            # Surface logical failures: if result has ok=False, alert + log.
            # Without this, /process-one/async returns ok:false silently
            # because HTTP-level the job "completed".
            if isinstance(out, dict) and out.get("ok") is False:
                detail = ""
                if "video_id" in out:
                    detail = f" video={out.get('video_id')} podcast={out.get('podcast')}"
                tail = captured_logs[-1500:] if captured_logs else "(no logs captured)"
                _log.warning(
                    "job_returned_ok_false",
                    extra={"job_id": job_id, "type": job_type, "result": out},
                )
                _notify_slack(
                    f":warning: Operators Vault {job_type} returned ok:false{detail}\n"
                    f"Job: {job_id}\nTail logs:\n```\n{tail}\n```"
                )
        except HTTPException as e:
            err_str = f"{e.status_code}: {e.detail}"
            captured_logs = _drain_logs()
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = err_str
                _jobs[job_id]["updated_at"] = time.time()
                _jobs[job_id]["logs"] = {
                    "stdout": buf_out.getvalue()[-8000:],
                    "stderr": (buf_err.getvalue() + "\n" + traceback.format_exc())[-8000:],
                    "captured": captured_logs,
                }
            log_job_event(job_id, "failed", {"type": job_type, "error": err_str})
            _notify_slack(f":rotating_light: Operators Vault sync failed\nJob: {job_type}\nError: {err_str[:200]}")
        except Exception as e:
            err_str = f"{type(e).__name__}: {e!s}"
            captured_logs = _drain_logs()
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = err_str
                _jobs[job_id]["updated_at"] = time.time()
                _jobs[job_id]["logs"] = {
                    "stdout": buf_out.getvalue()[-8000:],
                    "stderr": (buf_err.getvalue() + "\n" + traceback.format_exc())[-8000:],
                    "captured": captured_logs,
                }
            log_job_event(job_id, "failed", {"type": job_type, "error": err_str})
            _notify_slack(f":rotating_light: Operators Vault sync failed\nJob: {job_type}\nError: {err_str[:200]}")
        finally:
            heartbeat_stop.set()
            try:
                root_logger.removeHandler(log_handler)
                log_handler.close()
            except Exception:
                pass

    t = threading.Thread(target=run, daemon=True, name=f"job-{job_id[:8]}")
    t.start()


def _async_202_response(job_id: str, job_type: str) -> JSONResponse:
    """Return 202 with job_id; minimal response so Railway proxy gets a quick answer."""
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "running", "type": job_type, "jobs": f"/jobs/{job_id}"},
        headers={"Connection": "close", "Cache-Control": "no-store"},
    )


def _is_job_stale(j: dict) -> bool:
    """Check if a running job has gone stale (no heartbeat update within threshold)."""
    if j.get("status") != "running":
        return False
    updated = j.get("updated_at") or j.get("started_at") or 0
    return (time.time() - updated) > _STALE_JOB_TIMEOUT_SEC


def _mark_stale_jobs_failed() -> int:
    """Mark any running jobs that have gone stale as failed. Returns count of jobs marked."""
    count = 0
    with _jobs_lock:
        for jid, j in _jobs.items():
            if _is_job_stale(j):
                j["status"] = "error"
                j["error"] = f"Stale: no heartbeat for {_STALE_JOB_TIMEOUT_SEC}s (likely container restart)"
                j["updated_at"] = time.time()
                count += 1
                log_job_event(jid, "failed", {"type": j.get("type"), "reason": "stale_timeout"})
    if count:
        _log.warning("Marked %d stale jobs as failed", count)
    return count


def _running_job_id(job_type: str) -> str | None:
    """If a non-stale job of the given type is already running, return its job_id; else None.
    Caller must hold _jobs_lock."""
    for jid, j in _jobs.items():
        if j.get("type") == job_type and j.get("status") == "running" and not _is_job_stale(j):
            return jid
    return None


@app.post("/sync/async")
def sync_async():
    """Like POST /sync but returns 202 Accepted with job_id. Poll GET /jobs/{job_id} for status. Good when sync is slow. Only one sync at a time."""
    try:
        _mark_stale_jobs_failed()
        with _jobs_lock:
            existing = _running_job_id("sync")
            if existing is not None:
                _log.info("Sync already running, returning existing job", extra={"job_id": existing})
                return _async_202_response(existing, "sync")
        job_id = str(uuid.uuid4())
        _run_async_job(job_id, lambda: _do_sync(job_id=job_id), "sync")
        return _async_202_response(job_id, "sync")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {e!s}")


@app.post("/process-new/async")
def process_new_async():
    """Like POST /process-new but returns 202 Accepted with job_id. Poll GET /jobs/{job_id} for status. Only one process-new at a time."""
    try:
        _mark_stale_jobs_failed()
        with _jobs_lock:
            existing = _running_job_id("process-new")
            if existing is not None:
                _log.info("process-new already running, returning existing job", extra={"job_id": existing})
                return _async_202_response(existing, "process-new")
        job_id = str(uuid.uuid4())
        _run_async_job(job_id, lambda: _do_process_new(job_id=job_id), "process-new")
        return _async_202_response(job_id, "process-new")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start process-new: {e!s}")


@app.post("/process-one/async")
def process_one_async(req: ProcessRequest):
    """Process exactly one video asynchronously. Returns 202 + job_id; poll /jobs/{job_id}."""
    try:
        job_id = str(uuid.uuid4())

        def run_one():
            ok = _process_one(req.video_id, req.podcast)
            return {"ok": bool(ok), "video_id": req.video_id, "podcast": req.podcast}

        _run_async_job(job_id, run_one, "process-one")
        return _async_202_response(job_id, "process-one")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start process-one: {e!s}")


def _check_trigger_key() -> bool:
    """Optional: require SYNC_TRIGGER_KEY for GET trigger endpoints (set in Railway)."""
    key = (os.environ.get("SYNC_TRIGGER_KEY") or "").strip()
    return key == "" or key == "skip"  # no key or empty = allow; set key in Railway to require it


@app.get("/trigger-sync")
def trigger_sync_get(key: str | None = None):
    """GET trigger for sync (cron/n8n). Returns 202 + job_id. Optional: ?key=SYNC_TRIGGER_KEY (set in Railway). Only one sync at a time."""
    if os.environ.get("SYNC_TRIGGER_KEY") and (key or "").strip() != os.environ.get("SYNC_TRIGGER_KEY", ""):
        raise HTTPException(status_code=401, detail="Invalid or missing key")
    try:
        _mark_stale_jobs_failed()
        with _jobs_lock:
            existing = _running_job_id("sync")
            if existing is not None:
                _log.info("Sync already running (trigger), returning existing job", extra={"job_id": existing})
                return _async_202_response(existing, "sync")
        job_id = str(uuid.uuid4())
        _run_async_job(job_id, lambda: _do_sync(job_id=job_id), "sync")
        return _async_202_response(job_id, "sync")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {e!s}")


@app.get("/trigger-process-new")
def trigger_process_new_get(key: str | None = None):
    """GET trigger for process-new (cron/n8n). Returns 202 + job_id. Optional: ?key=SYNC_TRIGGER_KEY. Only one process-new at a time."""
    if os.environ.get("SYNC_TRIGGER_KEY") and (key or "").strip() != os.environ.get("SYNC_TRIGGER_KEY", ""):
        raise HTTPException(status_code=401, detail="Invalid or missing key")
    try:
        _mark_stale_jobs_failed()
        with _jobs_lock:
            existing = _running_job_id("process-new")
            if existing is not None:
                _log.info("process-new already running (trigger), returning existing job", extra={"job_id": existing})
                return _async_202_response(existing, "process-new")
        job_id = str(uuid.uuid4())
        _run_async_job(job_id, lambda: _do_process_new(job_id=job_id), "process-new")
        return _async_202_response(job_id, "process-new")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start process-new: {e!s}")


@app.post("/backfill")
async def backfill(request: Request):
    """
    Run backfill from seed_links (Supabase): seed into videos then process unprocessed.
    - With form files (9operators, marketing_operator, finance_operators, titans, or operators_and_titans): parse CSVs, upsert into seed_links, then run.
    - With no files: run from existing seed_links. Use POST /seed-links or /seed-links/csv first to store links.
    Returns 202 + job_id; poll GET /jobs/{job_id}.
    """
    from youtube_client import load_all_seed_csvs

    form = await request.form()
    tmpdir = Path(tempfile.mkdtemp(prefix="backfill_"))
    paths: dict[str, str] = {}
    for key in ("9operators", "marketing_operator", "finance_operators", "titans", "operators_and_titans"):
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
    out: dict = {
        "job_id": job_id,
        "status": j["status"],
        "type": j.get("type"),
        "worker_id": j.get("worker_id"),
        "started_at": datetime.fromtimestamp(j["started_at"], tz=timezone.utc).isoformat() if j.get("started_at") else None,
        "updated_at": datetime.fromtimestamp(j["updated_at"], tz=timezone.utc).isoformat() if j.get("updated_at") else None,
    }
    if j.get("result") is not None:
        out["result"] = j["result"]
    if j.get("error") is not None:
        out["error"] = j["error"]
    if j.get("logs") is not None:
        out["logs"] = j["logs"]
    if j.get("progress"):
        out["progress"] = j["progress"]
    return out


@app.get("/jobs")
def list_jobs(status: str | None = None):
    """List all jobs, optionally filtered by status (running, done, error). Most recent first."""
    with _jobs_lock:
        items = []
        for jid, j in _jobs.items():
            if status and j.get("status") != status:
                continue
            items.append({
                "job_id": jid,
                "status": j["status"],
                "type": j.get("type"),
                "worker_id": j.get("worker_id"),
                "started_at": datetime.fromtimestamp(j["started_at"], tz=timezone.utc).isoformat() if j.get("started_at") else None,
                "updated_at": datetime.fromtimestamp(j["updated_at"], tz=timezone.utc).isoformat() if j.get("updated_at") else None,
                "error": j.get("error"),
                "progress": j.get("progress"),
            })
    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return {"jobs": items, "total": len(items), "worker_id": _worker_id}


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
        "version": app.version,
        "worker_id": _worker_id,
        "docs": "/docs",
        "health": "/health",
        "stats": "/stats",
        "search": "/search",
        "search_ui": "/search-ui",
        "episodes": "/episodes",
        "episodes_ui": "/episodes-ui",
        "people": "/people",
        "people_ui": "/people-ui",
        "insights": "/insights",
        "insights_ui": "/insights-ui",
        "chat": "POST /chat",
        "ask_ui": "/ask-ui",
        "person": "/person/{slug}",
        "person_ui": "/person-ui/{slug}",
        "company": "/company/{slug}",
        "company_ui": "/company-ui/{slug}",
        "visuals": "/visuals",
        "related": "/related",
        "sync": "POST /sync",
        "sync_async": "POST /sync/async (202 + job, one at a time)",
        "process_new_async": "POST /process-new/async (202 + job, one at a time)",
        "process_one_async": "POST /process-one/async (body: video_id, podcast; 202 + job)",
        "trigger_sync": "GET /trigger-sync (?key= for cron, one at a time)",
        "trigger_process_new": "GET /trigger-process-new (?key= for cron, one at a time)",
        "seed_links": "POST /seed-links (JSON), POST /seed-links/csv (multipart) — store links in Supabase seed_links",
        "backfill": "POST /backfill (optional multipart CSVs; or none to run from seed_links in DB; 202 + job)",
        "jobs_list": "GET /jobs (?status=running|done|error)",
        "jobs_detail": "GET /jobs/{job_id}",
        "ingest_newsletter": "POST /ingest-newsletter — ingest one email from n8n (body: email_id, source, author, subject, published_at, body_html, body_text)",
        "newsletters": "GET /newsletters — list newsletters (?source=, ?processed=, ?limit=)",
        "newsletter_insights": "GET /newsletter-insights — search insights (?q=, ?source=, ?category=, ?limit=)",
        "newsletter_sources": "GET /newsletter-sources — list active sources (DB-backed); POST /newsletter-sources — add new source {slug, author, gmail_query}",
        "channels": "GET /channels — list active YouTube channel configs (DB-backed); POST /channels — add new channel {slug, channel_handle, display_name}",
    }


# ── Newsletter endpoints ───────────────────────────────────────────────────────

# Background queue for async Claude extraction after fast email storage
import queue as _queue
_newsletter_extract_queue: _queue.Queue = _queue.Queue()
_newsletter_worker_started = False
_NEWSLETTER_WORKERS = 4  # parallel Claude extraction threads

_NEWSLETTER_MAX_RETRIES = int(os.environ.get("NEWSLETTER_MAX_RETRIES", "3"))


def _newsletter_extract_worker():
    """Background thread: pick up newsletter_ids and run Claude extraction.

    On failure, increment retry_count and re-queue up to _NEWSLETTER_MAX_RETRIES
    attempts. After that, dead-letter by marking processed=TRUE with last_error
    set so the row stops blocking the queue and is visible to ops.
    """
    import psycopg2
    from newsletter_ingestor import extract_newsletter_insights, store_newsletter_insights, chunk_text, _db_conn
    while True:
        try:
            newsletter_id, source, body_text = _newsletter_extract_queue.get(timeout=5)
            try:
                # Skip if already processed (handles duplicates in queue).
                # Also pull retry_count so we can apply the dead-letter cap.
                conn = _db_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT processed, COALESCE(retry_count, 0) FROM newsletters WHERE id = %s",
                        (newsletter_id,),
                    )
                    row = cur.fetchone()
                conn.close()
                if not row or row[0]:
                    _newsletter_extract_queue.task_done()
                    continue
                retry_count = int(row[1] or 0)
                try:
                    chunks = chunk_text(body_text)
                    all_insights = []
                    for chunk in chunks:
                        chunk_insights = extract_newsletter_insights(chunk)
                        for ins in chunk_insights:
                            ins["source_chunk"] = chunk[:500]
                        all_insights.extend(chunk_insights)
                    store_newsletter_insights(newsletter_id, source, all_insights)
                    _log.info(
                        "newsletter_extracted",
                        extra={"newsletter_id": newsletter_id, "insights": len(all_insights)},
                    )
                except Exception as e:
                    err_str = f"{type(e).__name__}: {e!s}"
                    new_retry = retry_count + 1
                    if new_retry < _NEWSLETTER_MAX_RETRIES:
                        # Bump retry counter, persist error, re-queue.
                        try:
                            conn2 = _db_conn()
                            with conn2.cursor() as cur2:
                                cur2.execute(
                                    "UPDATE newsletters SET retry_count = %s, last_error = %s, last_error_at = now() WHERE id = %s",
                                    (new_retry, err_str[:2000], newsletter_id),
                                )
                                conn2.commit()
                            conn2.close()
                        except Exception as upd_err:
                            _log.warning(
                                "newsletter_retry_update_failed",
                                extra={"newsletter_id": newsletter_id, "error": str(upd_err)},
                            )
                        _log.warning(
                            "newsletter_extract_retry",
                            extra={
                                "newsletter_id": newsletter_id,
                                "attempt": new_retry,
                                "max": _NEWSLETTER_MAX_RETRIES,
                                "error": err_str,
                            },
                        )
                        # Re-queue for another attempt.
                        _newsletter_extract_queue.put((newsletter_id, source, body_text))
                    else:
                        # Dead-letter: mark processed=TRUE so it stops blocking,
                        # but record the failure so it's visible to ops.
                        try:
                            conn2 = _db_conn()
                            with conn2.cursor() as cur2:
                                cur2.execute(
                                    "UPDATE newsletters SET retry_count = %s, last_error = %s, last_error_at = now(), processed = TRUE WHERE id = %s",
                                    (new_retry, err_str[:2000], newsletter_id),
                                )
                                conn2.commit()
                            conn2.close()
                        except Exception as upd_err:
                            _log.warning(
                                "newsletter_deadletter_update_failed",
                                extra={"newsletter_id": newsletter_id, "error": str(upd_err)},
                            )
                        _log.error(
                            "newsletter_extract_deadlettered",
                            extra={
                                "newsletter_id": newsletter_id,
                                "attempts": new_retry,
                                "error": err_str,
                            },
                        )
                        _notify_slack(
                            f":skull: Newsletter extraction dead-lettered after {new_retry} attempts\n"
                            f"newsletter_id: {newsletter_id}\nError: {err_str[:300]}"
                        )
            finally:
                _newsletter_extract_queue.task_done()
        except _queue.Empty:
            continue
        except Exception:
            continue

def _ensure_newsletter_worker():
    global _newsletter_worker_started
    if not _newsletter_worker_started:
        for i in range(_NEWSLETTER_WORKERS):
            t = threading.Thread(target=_newsletter_extract_worker, daemon=True, name=f"newsletter-extractor-{i}")
            t.start()
        _newsletter_worker_started = True


class NewsletterIngestRequest(BaseModel):
    email_id: str
    source: str                       # nik_sharma | taylor_holiday | matt_bertulli | chase_dimond | operators_newsletter
    author: str = ""
    subject: str = ""
    published_at: str | None = None   # ISO8601
    body_html: str = ""
    body_text: str = ""
    sender_email: str = ""            # fallback: infer source from sender


@app.post("/ingest-newsletter")
def ingest_newsletter(req: NewsletterIngestRequest):
    """
    Ingest one newsletter email. Called by n8n Gmail trigger.
    Stores email immediately, queues Claude extraction in background.
    Returns {email_id, newsletter_id, status} quickly without blocking on Claude.
    """
    from newsletter_ingestor import (
        infer_source_from_sender, NEWSLETTER_SOURCES,
        strip_html, clean_email_text, upsert_newsletter
    )

    source = req.source
    if (not source or source == "unknown") and req.sender_email:
        inferred = infer_source_from_sender(req.sender_email)
        if inferred:
            source = inferred

    if source not in NEWSLETTER_SOURCES and source != "unknown":
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'. Valid: {list(NEWSLETTER_SOURCES.keys())}")

    author = req.author or (NEWSLETTER_SOURCES.get(source, {}).get("author", source))

    try:
        # Clean body
        body_text = req.body_text
        if req.body_html and not body_text:
            body_text = strip_html(req.body_html)
        body_text = clean_email_text(body_text)

        if not body_text or len(body_text) < 100:
            return {"email_id": req.email_id, "status": "skipped", "reason": "body too short", "insights_count": 0}

        # Store immediately (non-blocking)
        newsletter_id, is_new = upsert_newsletter(
            req.email_id, source, author, req.subject, req.published_at, body_text
        )
        if not is_new:
            return {"email_id": req.email_id, "newsletter_id": newsletter_id, "status": "duplicate", "insights_count": 0}

        # Queue Claude extraction in background
        _ensure_newsletter_worker()
        _newsletter_extract_queue.put((newsletter_id, source, body_text))

        return {"email_id": req.email_id, "newsletter_id": newsletter_id, "status": "queued", "insights_count": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e!s}")


@app.post("/process-newsletters")
def process_newsletters(limit: int = 50):
    """
    Manually trigger Claude extraction for all unprocessed newsletters.
    Queues up to `limit` newsletters for background processing.
    """
    import psycopg2, os
    _ensure_newsletter_worker()
    from newsletter_ingestor import _db_conn

    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, source, body_text FROM newsletters WHERE processed = FALSE AND body_text IS NOT NULL ORDER BY created_at ASC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    queued = 0
    for row in rows:
        newsletter_id, source, body_text = str(row[0]), row[1], row[2]
        if body_text and len(body_text) >= 100:
            _newsletter_extract_queue.put((newsletter_id, source, body_text))
            queued += 1

    return {"queued": queued, "queue_size": _newsletter_extract_queue.qsize()}


@app.get("/newsletters")
def list_newsletters(
    source: str | None = None,
    processed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List newsletters. Filter by source and/or processed status."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=15)
        cur = conn.cursor()
        try:
            where = []
            params: list = []
            if source:
                where.append("source = %s")
                params.append(source)
            if processed is not None:
                where.append("processed = %s")
                params.append(processed)
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            params.extend([limit, offset])
            cur.execute(
                f"""
                SELECT id, email_id, source, author, subject, published_at, processed, created_at,
                       length(body_text) AS body_len
                FROM newsletters
                {where_sql}
                ORDER BY published_at DESC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                if r.get("published_at"):
                    r["published_at"] = r["published_at"].isoformat()
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return {"newsletters": rows, "count": len(rows), "offset": offset}
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/newsletters/{newsletter_id}")
def get_newsletter(newsletter_id: str):
    """Get a single newsletter with its full body text and all extracted insights."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, email_id, source, author, subject, published_at, processed, body_text
                FROM newsletters WHERE id = %s
                """,
                (newsletter_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Newsletter not found")
            newsletter = {
                "id": str(row[0]),
                "email_id": row[1],
                "source": row[2],
                "author": row[3],
                "subject": row[4],
                "published_at": row[5].isoformat() if row[5] else None,
                "processed": row[6],
                "body_text": row[7] or "",
            }
            # All insights from this newsletter
            cur.execute(
                """
                SELECT id, category, title, description
                FROM newsletter_insights
                WHERE newsletter_id = %s
                ORDER BY category, title
                """,
                (newsletter_id,),
            )
            newsletter["insights"] = [
                {"id": str(r[0]), "category": r[1], "title": r[2], "description": r[3]}
                for r in cur.fetchall()
            ]
            return newsletter
        finally:
            cur.close()
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/newsletter-insights")
def list_newsletter_insights(
    q: str | None = None,
    source: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search newsletter insights via Postgres FTS. Filter by source and/or category."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=15)
        cur = conn.cursor()
        try:
            where = []
            params: list = []
            if q:
                where.append("to_tsvector('english', coalesce(ni.title,'') || ' ' || coalesce(ni.description,'')) @@ websearch_to_tsquery('english', %s)")
                params.append(q)
            if source:
                where.append("ni.source = %s")
                params.append(source)
            if category:
                where.append("ni.category ILIKE %s")
                params.append(f"%{category}%")
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            params.extend([limit, offset])
            cur.execute(
                f"""
                SELECT ni.id, ni.source, ni.category, ni.title, ni.description,
                       n.subject, n.author, n.published_at, ni.newsletter_id::text
                FROM newsletter_insights ni
                JOIN newsletters n ON n.id = ni.newsletter_id
                {where_sql}
                ORDER BY n.published_at DESC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                if r.get("published_at"):
                    r["published_at"] = r["published_at"].isoformat()
            return {"insights": rows, "count": len(rows)}
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TopicGuideRequest(BaseModel):
    topic: str


@app.post("/topic-guide")
def topic_guide(body: TopicGuideRequest):
    """
    Generate a topic guide by searching the vault for the given topic,
    then compiling insights into a structured markdown guide via Haiku.
    Public — no auth required.
    """
    topic = (body.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")

    # Search all content types for this topic
    results = _search_postgres(topic, limit=15, type_="all")
    hits = results.get("hits", [])

    # Also search newsletter insights directly (they're included in "all" but let's be thorough)
    if not hits:
        raise HTTPException(status_code=404, detail=f"No content found on topic: {topic}")

    # Build context from hits
    context_parts = []
    sources = []
    for h in hits:
        t = h.get("headline_title") or h.get("title") or ""
        d = h.get("headline_description") or h.get("description") or h.get("text") or ""
        pod = (h.get("podcast") or h.get("source") or "").replace("_", " ")
        author = h.get("author") or pod
        if t or d:
            context_parts.append(f"**{t}** ({author}): {d[:400]}")
            sources.append({
                "id": h.get("id", ""),
                "title": t,
                "description": d,
                "source": pod,
                "type": h.get("type", ""),
                "podcast": h.get("podcast"),
                "video_id": h.get("video_id"),
                "author": author,
            })

    context = "\n\n".join(context_parts)
    prompt = (
        f"You are an expert DTC and eCommerce operator analyst. "
        f"Based on the following insights from industry experts, write a concise, actionable Topic Guide on: **{topic}**\n\n"
        f"Format the guide in markdown with:\n"
        f"- A 2-3 sentence executive summary\n"
        f"- 3-5 key sections with headers\n"
        f"- Bullet points under each section\n"
        f"- A 'Key Takeaways' section at the end\n\n"
        f"Draw directly from these insights (cite the source name where relevant):\n\n{context}\n\n"
        f"Write the guide now:"
    )

    agent_key = os.environ.get("AGENT_SERVER_API_KEY", "")
    try:
        headers = {"Content-Type": "application/json"}
        if agent_key:
            headers["Authorization"] = f"Bearer {agent_key}"
        agent_res = requests.post(
            "https://ent-agent-server-production.up.railway.app/complete",
            json={"prompt": prompt, "max_tokens": 1500},
            headers=headers,
            timeout=90,
        )
        agent_res.raise_for_status()
        data = agent_res.json()
        content = data.get("text") or data.get("completion") or data.get("content") or ""
        if not content:
            raise ValueError(f"Empty response from agent server: {data}")
        return {"topic": topic, "content": content, "sources": sources[:10], "ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Guide generation failed: {e!s}")


@app.get("/topic-guide/search")
def topic_guide_search(q: str = "", limit: int = 10):
    """Search vault for a topic and return raw hits (no LLM). Public — no auth required."""
    if not q:
        raise HTTPException(status_code=400, detail="q required")
    results = _search_postgres(q.strip(), limit=limit, type_="all")
    return results


@app.get("/newsletter-sources")
def newsletter_sources():
    """List all active newsletter sources from DB (falls back to hardcoded if DB unavailable)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from newsletter_ingestor import _NEWSLETTER_SOURCES_FALLBACK
        return {"sources": _NEWSLETTER_SOURCES_FALLBACK, "source": "fallback"}
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, author, gmail_query, active, created_at FROM newsletter_source_configs WHERE active = TRUE ORDER BY created_at"
            )
            rows = cur.fetchall()
        conn.close()
        sources = [
            {"slug": r[0], "author": r[1], "gmail_query": r[2], "active": r[3], "created_at": r[4].isoformat() if r[4] else None}
            for r in rows
        ]
        return {"sources": sources, "source": "db"}
    except Exception as e:
        from newsletter_ingestor import _NEWSLETTER_SOURCES_FALLBACK
        return {"sources": _NEWSLETTER_SOURCES_FALLBACK, "source": "fallback", "error": str(e)}


class NewsletterSourceCreateRequest(BaseModel):
    slug: str
    author: str
    gmail_query: str


@app.post("/newsletter-sources")
def newsletter_sources_create(req: NewsletterSourceCreateRequest):
    """Add a new newsletter source. Slug must be unique."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO newsletter_source_configs (slug, author, gmail_query)
                VALUES (%s, %s, %s)
                RETURNING id, slug, author, gmail_query, active, created_at
                """,
                (req.slug, req.author, req.gmail_query),
            )
            row = cur.fetchone()
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "source": {
                "id": str(row[0]),
                "slug": row[1],
                "author": row[2],
                "gmail_query": row[3],
                "active": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/channels")
def list_channels():
    """List all active YouTube channel configs from DB (falls back to hardcoded if DB unavailable)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from youtube_client import DEFAULT_CHANNEL_HANDLES
        return {"channels": [{"slug": k, "channel_handle": v, "display_name": k.replace("_", " ").title()} for k, v in DEFAULT_CHANNEL_HANDLES.items()], "source": "fallback"}
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, channel_handle, display_name, active, created_at FROM channel_configs WHERE active = TRUE ORDER BY created_at"
            )
            rows = cur.fetchall()
        conn.close()
        channels = [
            {"slug": r[0], "channel_handle": r[1], "display_name": r[2], "active": r[3], "created_at": r[4].isoformat() if r[4] else None}
            for r in rows
        ]
        return {"channels": channels, "source": "db"}
    except Exception as e:
        from youtube_client import DEFAULT_CHANNEL_HANDLES
        return {"channels": [{"slug": k, "channel_handle": v, "display_name": k.replace("_", " ").title()} for k, v in DEFAULT_CHANNEL_HANDLES.items()], "source": "fallback", "error": str(e)}


class ChannelCreateRequest(BaseModel):
    slug: str
    channel_handle: str
    display_name: str


@app.post("/channels")
def channels_create(req: ChannelCreateRequest):
    """Add a new YouTube channel config. Slug must be unique. Channel handle should not include @."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO channel_configs (slug, channel_handle, display_name)
                VALUES (%s, %s, %s)
                RETURNING id, slug, channel_handle, display_name, active, created_at
                """,
                (req.slug, req.channel_handle.lstrip("@"), req.display_name),
            )
            row = cur.fetchone()
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "channel": {
                "id": str(row[0]),
                "slug": row[1],
                "channel_handle": row[2],
                "display_name": row[3],
                "active": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
