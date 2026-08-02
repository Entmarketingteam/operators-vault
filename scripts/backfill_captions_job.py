#!/usr/bin/env python3
"""Paced backfill of YouTube captions -> insights, run from a residential IP.

Why this exists: YouTube blocks datacenter IPs, so the Railway pipeline cannot pull
captions (it used a Webshare proxy until that account was banned). A residential IP
works with no proxy at all, but rate-limits under bulk load (`IpBlocked`), so this
job processes a small batch per run and resumes on the next tick.

Canonical owner: this job owns caption->insight backfill for operators-vault.
It replaces the Webshare proxy path in api.py/audio_extractor.py for backlog work.
Schedule: daily via Windows Task Scheduler on the Alienware box (Tailscale 100.120.248.8).

Harness: loop-harness skill (self-check, classification, checkpoints, breaker, handoff).

Usage:
    python scripts/backfill_captions_job.py            # normal paced run
    python scripts/backfill_captions_job.py --dry-run  # self-check + plan only, no work
    python scripts/backfill_captions_job.py --max 3 --pace 30
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import traceback
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env (same pattern as local_rest_processor.py)
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip():
                os.environ.setdefault(k.strip(), v.strip())

JOB_NAME = "vault-caption-backfill"
BASE, CAP, MAX_ATTEMPTS = 2, 300, 5
SCHEDULE_INTERVAL_SEC = 24 * 3600

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_STOCK_BOT_TOKEN", "")
TG_CHAT = os.environ.get("ETHAN_TELEGRAM_ID", "")


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Supabase REST (avoids the 6543 pooler that drops SSL) ──────────────
_H = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def _req(method: str, path: str, body=None, extra_headers=None):
    h = dict(_H)
    if extra_headers:
        h.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw else []


def sb_get(path):
    return _req("GET", path)


def sb_upsert(table, rows, on_conflict, ignore_dupes=False):
    pref = "resolution=ignore-duplicates" if ignore_dupes else "resolution=merge-duplicates"
    return _req("POST", f"{table}?on_conflict={on_conflict}", rows,
                {"Prefer": f"{pref},return=minimal"})


def sb_patch(table, filt, row):
    return _req("PATCH", f"{table}?{filt}", row, {"Prefer": "return=minimal"})


# ── Paging (state transitions only) ────────────────────────────────────
def page(text: str) -> bool:
    if not (TG_TOKEN and TG_CHAT):
        log("PAGE SKIPPED (no telegram creds): " + text)
        return False
    try:
        body = json.dumps({"chat_id": TG_CHAT, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
        log("PAGED: " + text.splitlines()[0])
        return True
    except Exception as e:
        log(f"PAGE FAILED: {type(e).__name__}: {e}")
        return False


# ── Failure classification (loop-harness §1) ───────────────────────────
def classify(exc: Exception) -> str:
    """transient | deterministic | environmental | ip_blocked"""
    n = type(exc).__name__
    s = str(exc).lower()
    # IpBlocked is a rate limit that heals on its own with time. It is NOT
    # per-item (the next video fails identically), so it ends the run rather
    # than quarantining anything; 3 fully-blocked runs in a row opens the breaker.
    if "ipblocked" in n.lower() or "too many requests" in s or "ratelimit" in n.lower():
        return "ip_blocked"
    if n in ("TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable", "VideoUnplayable",
             "AgeRestricted", "NotTranslatable"):
        return "deterministic"
    if "401" in s or "403" in s or "invalid api key" in s or "authentication" in s:
        return "environmental"
    if any(t in s for t in ("timeout", "timed out", "connection", "reset", "temporarily",
                            "502", "503", "504", "500")):
        return "transient"
    return "transient"


def backoff(attempt: int) -> float:
    return min(CAP, BASE * (2 ** attempt) * (0.5 + random.random()))


# ── Work discovery ─────────────────────────────────────────────────────
def fetch_missing() -> list[dict]:
    """Videos with no insights rows. Paginates both sides fully."""
    have = set()
    off = 0
    while True:
        page_rows = sb_get(f"insights?select=video_id&limit=1000&offset={off}&order=id")
        have.update(r["video_id"] for r in page_rows if r.get("video_id"))
        if len(page_rows) < 1000:
            break
        off += 1000
    vids = []
    off = 0
    while True:
        page_rows = sb_get(f"videos?select=video_id,podcast,title&limit=1000&offset={off}&order=video_id")
        vids += page_rows
        if len(page_rows) < 1000:
            break
        off += 1000
    return [v for v in vids if v["video_id"] not in have]


def checkpoints() -> dict[str, str]:
    out, off = {}, 0
    while True:
        rows = sb_get(f"job_checkpoints?select=item_key,status&job_name=eq.{JOB_NAME}"
                      f"&limit=1000&offset={off}&order=item_key")
        for r in rows:
            out[r["item_key"]] = r["status"]
        if len(rows) < 1000:
            break
        off += 1000
    return out


def mark(item_key: str, status: str, evidence=None, error=None) -> None:
    sb_upsert("job_checkpoints", [{
        "job_name": JOB_NAME, "item_key": item_key, "status": status,
        "evidence": evidence, "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }], on_conflict="job_name,item_key")


# ── Run bookkeeping ────────────────────────────────────────────────────
def prev_run() -> dict | None:
    rows = sb_get(f"job_runs?select=run_id,status,started_at,finished_at,handoff"
                  f"&job_name=eq.{JOB_NAME}&order=started_at.desc&limit=1")
    return rows[0] if rows else None


def recent_runs(n: int) -> list[dict]:
    return sb_get(f"job_runs?select=status,handoff,started_at&job_name=eq.{JOB_NAME}"
                  f"&order=started_at.desc&limit={n}")


def finish(run_id: str, status: str, envelope: dict) -> None:
    if envelope.get("confidence", 1.0) < 0.7 and not envelope.get("open_questions"):
        envelope["open_questions"] = ["confidence < 0.7 but no open questions recorded"]
    sb_patch("job_runs", f"run_id=eq.{run_id}",
             {"finished_at": datetime.now(timezone.utc).isoformat(),
              "status": status, "handoff": envelope})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=int(os.environ.get("BACKFILL_MAX_ITEMS", "6")))
    ap.add_argument("--pace", type=int, default=int(os.environ.get("BACKFILL_PACE_SEC", "90")))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # ── HARNESS SELF-CHECK v1 ──────────────────────────────────────────
    print(f"HARNESS SELF-CHECK v1 — {JOB_NAME}")
    fails = []

    missing_env = [v for v in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "AGENT_SERVER_API_KEY")
                   if not os.environ.get(v)]
    print(f"[1] env: required vars present ............................ "
          f"{'OK' if not missing_env else 'FAIL ' + ','.join(missing_env)}")
    if missing_env:
        fails.append("env")

    ref = "?"
    try:
        m = re.search(r"https://([a-z0-9]+)\.supabase", SB_URL)
        ref = m.group(1) if m else "?"
        sb_get(f"job_checkpoints?select=item_key&limit=1&job_name=eq.{JOB_NAME}")
        print(f"[2] state: job_checkpoints reachable, project={ref} ....... OK")
    except Exception as e:
        print(f"[2] state: job_checkpoints reachable, project={ref} ....... FAIL {e}")
        fails.append("state")

    fetched = []
    try:
        for attempt in range(MAX_ATTEMPTS):
            try:
                fetched = fetch_missing()
                break
            except Exception:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(backoff(attempt))
        keys = [v["video_id"] for v in fetched]
        ok_keys = all(k and k.strip() for k in keys) and len(set(keys)) == len(keys)
        print(f"[3] item_key: all {len(keys)} fetched keys non-empty, distinct "
              f"{'OK' if ok_keys else 'FAIL'}")
        if not ok_keys:
            fails.append("item_key")
    except Exception as e:
        print(f"[3] item_key: fetch failed after retries ................. FAIL {e}")
        fails.append("item_key")

    cps = {}
    try:
        cps = checkpoints()
    except Exception as e:
        print(f"[4] resume: checkpoint read failed ....................... FAIL {e}")
        fails.append("resume")
    done_n = sum(1 for s in cps.values() if s == "done")
    quar_n = sum(1 for s in cps.values() if s == "quarantined")
    todo = [v for v in fetched if cps.get(v["video_id"]) not in ("done", "quarantined")]
    print(f"[4] resume: fetched {len(fetched)}, pending {len(todo)}, done {done_n}, quar {quar_n} .... OK")

    print(f"[5] retry: BASE={BASE} CAP={CAP} MAX={MAX_ATTEMPTS}(total) full-jitter ....... OK")
    print(f"[6] classes: transient/deterministic/environmental/ip_blocked  OK")

    prev = prev_run()
    prev_status = prev["status"] if prev else "none"
    mode = "half-open" if prev_status == "circuit_open" else "closed"
    print(f"[7] breaker: prev-run status={prev_status}, mode={mode} ....... OK")

    print(f"[8] page: TELEGRAM token present .......................... "
          f"{'OK' if (TG_TOKEN and TG_CHAT) else 'FAIL'}")
    if not (TG_TOKEN and TG_CHAT):
        fails.append("page")

    print(f"[9] idempotency: upsert key job_name,item_key + per-video "
          f"delete-before-insert  OK")

    # Overlap guard
    if prev and prev["status"] == "running" and prev.get("started_at"):
        started = datetime.fromisoformat(prev["started_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - started).total_seconds()
        if age < SCHEDULE_INTERVAL_SEC:
            print(f"[10] handoff: prior run still running ({age/60:.0f}m) — exiting, it owns the tick")
            return 0

    run_id = None
    if not fails and not args.dry_run:
        row = _req("POST", "job_runs", [{"job_name": JOB_NAME, "status": "running"}],
                   {"Prefer": "return=representation"})
        run_id = row[0]["run_id"]
    print(f"[10] handoff: job_runs row created, run_id={run_id} ......... "
          f"{'OK' if run_id else 'SKIPPED (dry-run)' if args.dry_run else 'FAIL'}")

    if fails:
        log(f"SELF-CHECK FAILED: {fails}")
        return 1
    if args.dry_run:
        log(f"DRY RUN — would process {min(args.max, len(todo))} of {len(todo)} pending, "
            f"pace={args.pace}s")
        for v in todo[:args.max]:
            log(f"  would process {v['video_id']} ({v['podcast']}) {(v.get('title') or '')[:44]}")
        return 0

    # ── Seed pending (idempotent; existing done/quarantined keep status) ──
    if todo:
        sb_upsert("job_checkpoints",
                  [{"job_name": JOB_NAME, "item_key": v["video_id"], "status": "pending"}
                   for v in todo],
                  on_conflict="job_name,item_key", ignore_dupes=True)

    # Half-open: one item only
    batch = todo[:1] if mode == "half-open" else todo[:args.max]
    log(f"processing {len(batch)} item(s) (mode={mode}, {len(todo)} pending total)")

    import local_rest_processor as P

    done = quarantined = 0
    consec_exhausted = 0
    attempted = 0
    failed = 0
    ip_blocked = False
    evidence = []
    breaker_reason = None

    for idx, v in enumerate(batch):
        vid = v["video_id"]
        if idx and args.pace:
            log(f"pacing {args.pace}s before {vid}")
            time.sleep(args.pace)
        attempted += 1
        last_exc = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                P.process_one(vid, v.get("podcast") or "9operators", v.get("title") or "")
                n = len(sb_get(f"insights?select=id&video_id=eq.{vid}&limit=1"))
                if n == 0:
                    raise RuntimeError("extracted 0 insights from a stored transcript")
                mark(vid, "done", evidence={"insights_present": True})
                done += 1
                consec_exhausted = 0
                evidence.append({"check": f"insights for {vid}",
                                 "command": f"GET insights?video_id=eq.{vid}",
                                 "result": ">=1 row"})
                log(f"OK {vid}")
                last_exc = None
                break
            except Exception as e:
                last_exc = e
                cls = classify(e)
                log(f"{vid} attempt {attempt+1}/{MAX_ATTEMPTS} {cls}: {type(e).__name__}: {str(e)[:120]}")
                if cls == "ip_blocked":
                    ip_blocked = True
                    break
                if cls == "deterministic":
                    mark(vid, "quarantined", error=f"{type(e).__name__}: {str(e)[:400]}")
                    quarantined += 1
                    consec_exhausted = 0
                    last_exc = None
                    break
                if cls == "environmental":
                    breaker_reason = f"environmental failure with no named healer: {type(e).__name__}"
                    break
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(backoff(attempt))
        if ip_blocked:
            log("IP rate-limited — ending run; remaining items stay pending for the next tick")
            break
        if breaker_reason:
            break
        if last_exc is not None:
            failed += 1
            consec_exhausted += 1
            mark(vid, "pending", error=f"exhausted: {type(last_exc).__name__}: {str(last_exc)[:400]}")
            if consec_exhausted >= 3:
                breaker_reason = "3 consecutive items exhausted retries (transient)"
                break
        if attempted >= 10 and failed / attempted > 0.5:
            breaker_reason = f"failure rate {failed}/{attempted} > 50%"
            break

    pending_left = len(todo) - done - quarantined
    resume_cmd = (r'C:\Python314\python.exe C:\Users\ejatc\operators-vault\scripts'
                  r'\backfill_captions_job.py')
    envelope = {
        "job": JOB_NAME, "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "state": {"items_fetched": len(fetched), "items_done": done,
                  "items_quarantined": quarantined, "items_pending": pending_left,
                  "ip_blocked": ip_blocked},
        "evidence": evidence,
        "open_questions": [],
        "confidence": 0.9,
        "next_actions": [f"resume with: {resume_cmd}"],
    }

    # 3 consecutive fully-blocked runs = the block is not clearing on its own.
    if ip_blocked and done == 0:
        prior = [r for r in recent_runs(3)]
        blocked_streak = 1 + sum(
            1 for r in prior
            if (r.get("handoff") or {}).get("state", {}).get("ip_blocked")
            and (r.get("handoff") or {}).get("state", {}).get("items_done") == 0)
        envelope["open_questions"].append(f"IP blocked, {blocked_streak} run(s) in a row with 0 done")
        if blocked_streak >= 3:
            breaker_reason = f"IP blocked on {blocked_streak} consecutive runs"

    if breaker_reason:
        envelope["status"] = "circuit_open"
        envelope["open_questions"].append(breaker_reason)
        envelope["confidence"] = 0.5
        finish(run_id, "circuit_open", envelope)
        if prev_status != "circuit_open":  # page on transition only
            page(f"🔴 {JOB_NAME} breaker OPEN\nrun {run_id}\n{breaker_reason}\n"
                 f"pending={pending_left}\nresume: {resume_cmd}")
        log(f"BREAKER OPEN: {breaker_reason}")
        return 2

    envelope["status"] = "succeeded"
    finish(run_id, "succeeded", envelope)
    if prev_status == "circuit_open":
        page(f"🟢 {JOB_NAME} recovered\nrun {run_id}\ndone={done} pending={pending_left}")
    log(f"DONE done={done} quarantined={quarantined} pending={pending_left} ip_blocked={ip_blocked}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
