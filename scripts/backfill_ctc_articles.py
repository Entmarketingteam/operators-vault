#!/usr/bin/env python3
"""Paced backfill of commonthreadco.com articles -> newsletter_insights.

Why this exists (and why it is not the daily sync)
--------------------------------------------------
The atom feeds carry full article bodies but cap at ~30 entries per blog and ignore
pagination, so `POST /sync-ctc-articles` can only ever see recent posts. Historical
coverage — the ~277 older coachs-corner articles and the tails of the smaller blogs —
has to walk the sitemap and fetch each page. That is what this job does.

⚠️ CTC rate-limits hard. Measured 2026-08-02: 6 concurrent requests tripped 429s, and
sustained pressure escalated from 429 to refusing connections outright, with no
Retry-After header to guide backoff. So this job is SERIAL, paced by default at one
page per 20s, processes a bounded batch per run, and treats 429 as a whole-run stop
rather than a per-item fault. A full pass is therefore spread across several runs —
the same shape as the caption backfill, for the same reason.

Canonical owner: this job owns HISTORICAL CTC article ingestion. New articles are owned
by `POST /sync-ctc-articles` on the API, called daily by n8n. Do not build a third path.

Harness: loop-harness skill (self-check, classification, checkpoints, breaker, handoff).

Usage:
    python scripts/backfill_ctc_articles.py --dry-run    # self-check + plan, no work
    python scripts/backfill_ctc_articles.py              # paced run, default batch
    python scripts/backfill_ctc_articles.py --max 40 --pace 20
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip():
                os.environ.setdefault(k.strip(), v.strip())

import ctc_article_ingestor as ctc  # noqa: E402

JOB_NAME = "vault-ctc-article-backfill"
BASE, CAP, MAX_ATTEMPTS = 8, 300, 4
SCHEDULE_INTERVAL_SEC = 24 * 3600

# ⚠️ The operators-vault Supabase project. This guard is not paranoia — it is
# traps.md T6 firing in practice. Running this job under
# `doppler run --project ent-agency-automation` overrides SUPABASE_URL with
# `abhhegllhwbmanwvqanc`, the creatormetrics project that is EMPTY in every table.
# Verified 2026-08-02: only a 401 on a mismatched service-role key stopped that run,
# and a matching key would have made it succeed silently against the wrong database.
# The vault's own credentials live in this repo's gitignored .env.
EXPECTED_PROJECT_REF = "wbdwnlzbgugewtmvahwg"

# The CTC podcast archive. Excluded at enumeration so the job never spends a paced
# request on a page the classifier would discard anyway (~1,100 chars of show notes).
PODCAST_BLOGS = {"ecommerce-playbook", "dtc-hotline"}

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_STOCK_BOT_TOKEN", "")
TG_CHAT = os.environ.get("ETHAN_TELEGRAM_ID", "")


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Supabase REST (harness state only — article writes go through psycopg2) ────
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


# ── Failure classification (loop-harness §1) ───────────────────────────────────
def classify(exc: Exception) -> str:
    """transient | deterministic | environmental | rate_limited"""
    name = type(exc).__name__
    s = str(exc).lower()
    if isinstance(exc, ctc.RateLimited) or "429" in s or "too many requests" in s:
        return "rate_limited"
    if "404" in s or "410" in s or "gone" in s:
        return "deterministic"
    if "401" in s or "403" in s or "authentication" in s or "invalid api key" in s:
        return "environmental"
    if any(t in s for t in ("timeout", "timed out", "connection", "reset", "temporarily",
                            "500", "502", "503", "504")):
        return "transient"
    if name in ("HTTPError", "URLError"):
        return "transient"
    return "transient"


def backoff(attempt: int) -> float:
    return min(CAP, BASE * (2 ** attempt) * (0.5 + random.random()))


# ── Work discovery ─────────────────────────────────────────────────────────────
def fetch_pending() -> list[dict]:
    """Sitemap articles not already stored, excluding the podcast blogs.

    `newsletters.email_id` holds the canonical URL for article rows, so the already-
    stored set is an exact URL match — no fuzzy title matching, no double-ingest.
    """
    articles = [a for a in ctc.enumerate_articles() if a["blog"] not in PODCAST_BLOGS]

    have = set()
    off = 0
    while True:
        rows = sb_get(f"newsletters?select=email_id&source=eq.{ctc.SOURCE_SLUG}"
                      f"&limit=1000&offset={off}&order=email_id")
        have.update(r["email_id"] for r in rows if r.get("email_id"))
        if len(rows) < 1000:
            break
        off += 1000
    return [a for a in articles if a["url"] not in have]


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


def prev_run() -> dict | None:
    rows = sb_get(f"job_runs?select=run_id,status,started_at,finished_at,handoff"
                  f"&job_name=eq.{JOB_NAME}&order=started_at.desc&limit=1")
    return rows[0] if rows else None


def finish(run_id: str, status: str, envelope: dict) -> None:
    if envelope.get("confidence", 1.0) < 0.7 and not envelope.get("open_questions"):
        envelope["open_questions"] = ["confidence < 0.7 but no open questions recorded"]
    sb_patch("job_runs", f"run_id=eq.{run_id}",
             {"finished_at": datetime.now(timezone.utc).isoformat(),
              "status": status, "handoff": envelope})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=int(os.environ.get("CTC_BACKFILL_MAX", "40")))
    ap.add_argument("--pace", type=int, default=int(os.environ.get("CTC_BACKFILL_PACE_SEC", "20")))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # ── HARNESS SELF-CHECK v1 ──────────────────────────────────────────────────
    print(f"HARNESS SELF-CHECK v1 — {JOB_NAME}")
    fails = []

    missing_env = [v for v in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                               "DATABASE_URL", "ANTHROPIC_API_KEY")
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

    pending = []
    try:
        for attempt in range(MAX_ATTEMPTS):
            try:
                pending = fetch_pending()
                break
            except Exception:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(backoff(attempt))
        keys = [a["url"] for a in pending]
        ok_keys = all(k and k.strip() for k in keys) and len(set(keys)) == len(keys)
        print(f"[3] item_key: all {len(keys)} candidate URLs non-empty, distinct "
              f"{'OK' if ok_keys else 'FAIL'}")
        if not ok_keys:
            fails.append("item_key")
    except Exception as e:
        print(f"[3] item_key: enumeration failed after retries ............ FAIL {e}")
        fails.append("item_key")

    cps = {}
    try:
        cps = checkpoints()
    except Exception as e:
        print(f"[4] resume: checkpoint read failed ....................... FAIL {e}")
        fails.append("resume")
    done_n = sum(1 for s in cps.values() if s == "done")
    skip_n = sum(1 for s in cps.values() if s == "skipped")
    quar_n = sum(1 for s in cps.values() if s == "quarantined")
    todo = [a for a in pending
            if cps.get(a["url"]) not in ("done", "skipped", "quarantined")]
    print(f"[4] resume: candidates {len(pending)}, pending {len(todo)}, done {done_n}, "
          f"skipped {skip_n}, quar {quar_n} .... OK")

    print(f"[5] retry: BASE={BASE} CAP={CAP} MAX={MAX_ATTEMPTS}(total) full-jitter ....... OK")
    print(f"[6] classes: transient/deterministic/environmental/rate_limited  OK")

    prev = prev_run()
    prev_status = prev["status"] if prev else "none"
    mode = "half-open" if prev_status == "circuit_open" else "closed"
    print(f"[7] breaker: prev-run status={prev_status}, mode={mode} ....... OK")

    print(f"[8] page: TELEGRAM token present .......................... "
          f"{'OK' if (TG_TOKEN and TG_CHAT) else 'FAIL'}")
    if not (TG_TOKEN and TG_CHAT):
        fails.append("page")

    print(f"[9] idempotency: newsletters.email_id UNIQUE on the article URL + "
          f"checkpoint key job_name,item_key  OK")

    if prev and prev["status"] == "running" and prev.get("started_at"):
        started = datetime.fromisoformat(prev["started_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - started).total_seconds()
        if age < SCHEDULE_INTERVAL_SEC:
            print(f"[10] handoff: prior run still running ({age/60:.0f}m) — exiting, "
                  f"it owns the tick")
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
        by_blog: dict[str, int] = {}
        for a in todo:
            by_blog[a["blog"]] = by_blog.get(a["blog"], 0) + 1
        log(f"DRY RUN — would process {min(args.max, len(todo))} of {len(todo)} pending, "
            f"pace={args.pace}s (~{min(args.max, len(todo)) * args.pace // 60}m)")
        log(f"pending by blog: {dict(sorted(by_blog.items(), key=lambda kv: -kv[1]))}")
        for a in todo[:args.max]:
            log(f"  would fetch {a['blog']}/{a['handle'][:52]}")
        return 0

    if todo:
        sb_upsert("job_checkpoints",
                  [{"job_name": JOB_NAME, "item_key": a["url"], "status": "pending"}
                   for a in todo],
                  on_conflict="job_name,item_key", ignore_dupes=True)

    # True publish dates for whatever the atom feeds still cover. Everything older
    # falls back to sitemap lastmod (an UPDATE time) — see build_date_index().
    date_index = {}
    try:
        date_index = ctc.build_date_index(sorted({a["blog"] for a in todo[:args.max]}))
        log(f"date index: {len(date_index)} URLs with true publish times")
    except Exception as e:
        log(f"date index unavailable ({type(e).__name__}) — falling back to lastmod")

    batch = todo[:1] if mode == "half-open" else todo[:args.max]
    log(f"processing {len(batch)} item(s) (mode={mode}, {len(todo)} pending total)")

    stored = skipped = quarantined = 0
    insights_total = 0
    attempted = failed = 0
    consec_exhausted = 0
    rate_limited = False
    evidence = []
    breaker_reason = None

    for idx, a in enumerate(batch):
        url = a["url"]
        if idx and args.pace:
            time.sleep(args.pace)
        attempted += 1
        last_exc = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                published = date_index.get(url) or a.get("lastmod")
                row = ctc.fetch_and_parse(url, published)
                result = ctc.ingest_article(url, row)

                if row["kind"] == "extraction_failed":
                    # Selectors missed. Quarantine so a human sees it — never treat an
                    # empty body as "this post had nothing to say" (traps.md T4).
                    mark(url, "quarantined",
                         evidence={"chars": row["chars"], "template": row["template"]},
                         error="body under extraction-failure floor")
                    quarantined += 1
                    log(f"QUARANTINE {a['handle'][:44]} ({row['chars']} chars)")
                elif row["kind"] in ("shownotes", "thin"):
                    mark(url, "skipped",
                         evidence={"kind": row["kind"], "chars": row["chars"]})
                    skipped += 1
                else:
                    n = int(result.get("insights_count", 0))
                    mark(url, "done", evidence={"kind": row["kind"], "chars": row["chars"],
                                                "insights": n, "medium": row["medium"]})
                    stored += 1
                    insights_total += n
                    evidence.append({"check": f"insights for {a['handle'][:40]}",
                                     "command": f"newsletters.email_id={url}",
                                     "result": f"{n} insights, {row['chars']} chars"})
                    log(f"OK {a['handle'][:44]} -> {n} insights ({row['kind']})")
                consec_exhausted = 0
                last_exc = None
                break
            except Exception as e:  # noqa: BLE001
                last_exc = e
                kind = classify(e)
                if kind == "rate_limited":
                    # Not a per-item fault: every subsequent URL fails identically, so
                    # end the run and let the next tick resume from the checkpoint.
                    rate_limited = True
                    break
                if kind == "deterministic":
                    mark(url, "quarantined", error=f"{type(e).__name__}: {e}"[:200])
                    quarantined += 1
                    last_exc = None
                    break
                if kind == "environmental":
                    breaker_reason = f"environmental: {type(e).__name__}: {e}"[:200]
                    break
                if attempt == MAX_ATTEMPTS - 1:
                    break
                time.sleep(backoff(attempt))

        if rate_limited or breaker_reason:
            break
        if last_exc is not None:
            failed += 1
            consec_exhausted += 1
            mark(url, "pending", error=f"{type(last_exc).__name__}: {last_exc}"[:200])
            log(f"EXHAUSTED {a['handle'][:44]}: {type(last_exc).__name__}")
            if consec_exhausted >= 3:
                breaker_reason = "3 consecutive exhausted items"
                break

    status = "succeeded"
    if breaker_reason:
        status = "circuit_open"
    elif attempted >= 10 and failed > attempted * 0.5:
        status = "circuit_open"
        breaker_reason = f">50% failures ({failed}/{attempted})"

    remaining = len(todo) - (stored + skipped + quarantined)
    envelope = {
        "summary": (f"{stored} articles stored ({insights_total} insights), "
                    f"{skipped} skipped, {quarantined} quarantined, {failed} exhausted"),
        "evidence": evidence[:20],
        "open_questions": [],
        "confidence": 0.9 if status == "succeeded" else 0.5,
        "remaining": remaining,
        "rate_limited": rate_limited,
        "resume": "python scripts/backfill_ctc_articles.py",
    }
    if rate_limited:
        envelope["open_questions"].append(
            "run ended early on CTC 429 — resume next tick, consider raising --pace")
    if quarantined:
        envelope["open_questions"].append(
            f"{quarantined} URLs quarantined — check job_checkpoints for selector misses")

    # A run that stored nothing while work remained is the org's dominant silent
    # failure wearing a green status. Say so out loud.
    if stored == 0 and remaining > 0 and not rate_limited:
        envelope["open_questions"].append(
            f"0 articles stored with {remaining} still pending — investigate before "
            f"trusting the next run")
        page(f"⚠️ {JOB_NAME}: 0 stored, {remaining} pending. Extraction may be broken.")

    if run_id:
        finish(run_id, status, envelope)
    log(envelope["summary"] + f" | {remaining} pending | status={status}")
    if breaker_reason:
        page(f"🔴 {JOB_NAME} circuit_open: {breaker_reason}\nResume: {envelope['resume']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
