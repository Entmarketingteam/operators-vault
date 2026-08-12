#!/usr/bin/env python3
"""Backfill start_time_sec/end_time_sec on existing `insights` rows.

Why this exists: 41,924 of 56,439 insights (74.3%) have NULL start_time_sec because
insight_extractor.extract_timestamps() failed silently during ingestion. This script
re-runs ONLY the timestamp step against each insight's already-stored transcript
segments — it does not touch title/description/category/framework.

Dry-run is the default: it calls the real extractor and prints what it WOULD write,
but performs no DB writes at all (no insights UPDATE, no job_runs/job_checkpoints
rows). Only --apply performs real UPDATEs and checkpoints progress.

Resumable via the job_runs/job_checkpoints harness tables (same pattern as
scripts/backfill_captions_job.py), so a kill/restart picks up where it left off
instead of reprocessing rows 1..N. Concurrency is a small fixed worker pool
(ThreadPoolExecutor, default 3) pulling items continuously — no burst-then-sleep
(see traps.md T14b).

Usage:
    python scripts/backfill_insight_timestamps.py --limit 10                # dry run
    python scripts/backfill_insight_timestamps.py --apply --limit 5         # real writes
    python scripts/backfill_insight_timestamps.py --apply --job-id <uuid>   # resume a run
    python scripts/backfill_insight_timestamps.py --apply --workers 5       # full backfill
"""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env (same pattern as backfill_captions_job.py / pipeline.py's fallback)
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip():
                os.environ.setdefault(k.strip(), v.strip())

import db_utils
from pipeline import _format_timestamped
from insight_extractor import extract_timestamps

JOB_NAME = "vault-insight-timestamp-backfill"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(JOB_NAME)

SEGMENTS_SQL = """
    SELECT s.start_time_sec, s.speaker_label, s.text
    FROM segments s
    JOIN transcriptions tr ON tr.id = s.transcription_id
    WHERE tr.video_id = %s
    ORDER BY s.start_time_sec
"""

PENDING_SQL = """
    SELECT i.id, i.video_id, i.title, i.description
    FROM insights i
    WHERE i.video_id IS NOT NULL
      AND i.start_time_sec IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM job_checkpoints c
        WHERE c.job_name = %s AND c.item_key = i.id::text AND c.status IN ('done', 'quarantined')
      )
    ORDER BY i.id
"""

# Formatted transcript is identical for every insight on the same video, so cache it
# per run instead of re-querying segments once per insight.
_cache_lock = threading.Lock()
_transcript_cache: dict[str, str | None] = {}


def _get_timestamped_transcript(video_id: str, conn) -> str | None:
    with _cache_lock:
        if video_id in _transcript_cache:
            return _transcript_cache[video_id]
    cur = conn.cursor()
    cur.execute(SEGMENTS_SQL, (video_id,))
    rows = cur.fetchall()
    cur.close()
    text = None
    if rows:
        utterances = [{"start": r[0], "speaker": r[1], "transcript": r[2]} for r in rows]
        text = _format_timestamped(utterances) or None
    with _cache_lock:
        _transcript_cache[video_id] = text
    return text


def _get_or_create_job(conn, job_id: str | None) -> str:
    cur = conn.cursor()
    if job_id:
        cur.execute("SELECT run_id FROM job_runs WHERE run_id = %s AND job_name = %s", (job_id, JOB_NAME))
        row = cur.fetchone()
        cur.close()
        if not row:
            raise SystemExit(f"--job-id {job_id} not found for job_name={JOB_NAME}")
        return str(row[0])
    cur.execute(
        "INSERT INTO job_runs (job_name, status) VALUES (%s, 'running') RETURNING run_id",
        (JOB_NAME,),
    )
    run_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    log.info("started job_runs row run_id=%s (resume later with --job-id %s)", run_id, run_id)
    return run_id


def _finish_job(conn, run_id: str, status: str, handoff: dict) -> None:
    from psycopg2.extras import Json
    cur = conn.cursor()
    cur.execute(
        "UPDATE job_runs SET finished_at = now(), status = %s, handoff = %s WHERE run_id = %s",
        (status, Json(handoff), run_id),
    )
    conn.commit()
    cur.close()


def _mark(conn, item_key: str, status: str, *, evidence: dict | None = None, error: str | None = None) -> None:
    from psycopg2.extras import Json
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO job_checkpoints (job_name, item_key, status, evidence, error, updated_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (job_name, item_key) DO UPDATE SET
          status = EXCLUDED.status, evidence = EXCLUDED.evidence, error = EXCLUDED.error,
          updated_at = now()
        """,
        (JOB_NAME, item_key, status, Json(evidence) if evidence is not None else None, error),
    )
    conn.commit()
    cur.close()


def _process_one(row: tuple, apply: bool, job_id: str | None) -> dict:
    insight_id, video_id, title, description = row
    insight_id = str(insight_id)
    result = {"id": insight_id, "video_id": video_id}
    conn = db_utils.connect()
    try:
        transcript = _get_timestamped_transcript(video_id, conn)
        if not transcript:
            result.update(status="unresolved", reason="no transcript segments for video")
            if apply:
                _mark(conn, insight_id, "quarantined", error="no transcript segments for video")
            return result

        desc_or_title = (description or "").strip() or (title or "").strip()
        start_sec, end_sec = extract_timestamps(transcript, desc_or_title, prompt_set="operators")

        if start_sec is None:
            result.update(status="unresolved", reason="extract_timestamps returned None")
            if apply:
                _mark(conn, insight_id, "quarantined", error="extract_timestamps returned None")
            return result

        result.update(status="resolved", start_sec=start_sec, end_sec=end_sec)
        if apply:
            cur = conn.cursor()
            cur.execute(
                "UPDATE insights SET start_time_sec = %s, end_time_sec = %s WHERE id = %s",
                (start_sec, end_sec, insight_id),
            )
            conn.commit()
            cur.close()
            _mark(conn, insight_id, "done",
                  evidence={"start_sec": start_sec, "end_sec": end_sec, "job_id": job_id})
        return result
    except Exception as e:
        log.warning("error processing insight %s (video %s): %s", insight_id, video_id, e)
        result.update(status="error", reason=str(e))
        if apply:
            try:
                _mark(conn, insight_id, "pending", error=f"{type(e).__name__}: {str(e)[:400]}")
            except Exception:
                pass
        return result
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform real UPDATEs (default: dry run)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="cap rows processed this run")
    ap.add_argument("--job-id", type=str, default=None, help="resume a prior job_runs run_id")
    args = ap.parse_args()

    if not db_utils.resolve_db_url():
        log.error("DATABASE_URL not set")
        return 1

    conn = db_utils.connect()
    job_id = _get_or_create_job(conn, args.job_id) if args.apply else args.job_id

    sql = PENDING_SQL
    params: tuple = (JOB_NAME,)
    if args.limit:
        sql += " LIMIT %s"
        params += (args.limit,)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.commit()  # release the AccessShareLock this SELECT holds instead of sitting
                   # idle-in-transaction for the whole run and blocking DDL elsewhere
    conn.close()

    log.info("%s: %d pending row(s) to process (apply=%s, workers=%d, job_id=%s)",
              JOB_NAME, len(rows), args.apply, args.workers, job_id)

    resolved = unresolved = errors = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_process_one, row, args.apply, job_id) for row in rows]
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            tag = "apply" if args.apply else "dry-run"
            if r["status"] == "resolved":
                resolved += 1
                verb = "UPDATED" if args.apply else "WOULD UPDATE"
                log.info("[%s] insight %s (video %s): NULL -> start=%.2f end=%s (%s)",
                          tag, r["id"], r["video_id"], r["start_sec"],
                          f'{r["end_sec"]:.2f}' if r["end_sec"] is not None else "None", verb)
            elif r["status"] == "unresolved":
                unresolved += 1
                log.info("[%s] insight %s (video %s): still unresolved (%s)",
                          tag, r["id"], r["video_id"], r["reason"])
            else:
                errors += 1
                log.warning("[%s] insight %s (video %s): ERROR %s",
                            tag, r["id"], r["video_id"], r["reason"])

    log.info("%s: done. resolved=%d unresolved=%d errors=%d of %d processed (apply=%s)",
              JOB_NAME, resolved, unresolved, errors, len(rows), args.apply)

    if args.apply:
        _finish_job(conn, job_id, "succeeded", {
            "job": JOB_NAME, "job_id": job_id,
            "state": {"processed": len(rows), "resolved": resolved,
                      "unresolved": unresolved, "errors": errors},
            "next_actions": [f"resume with: python scripts/backfill_insight_timestamps.py --apply --job-id {job_id}"],
        })

    conn.close()
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
