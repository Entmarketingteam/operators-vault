#!/usr/bin/env python3
"""Extract insights for newsletters that have none.

Why this exists
---------------
`_newsletter_extract_worker` in api.py died on every job from ~2026-05 because it
selected `retry_count`, a column no migration ever created. Raw newsletter bodies
kept landing; nothing became a searchable insight. Migration
20260801_newsletter_extraction_repair.sql fixes the column; this drains the backlog
it left behind.

Resumability comes from the selection criterion itself: rows are chosen by
"has no rows in newsletter_insights", so a crashed or killed run simply picks up
where it stopped on the next invocation. No checkpoint table needed.

Dry-run is the default (traps.md T4). Pass --apply to write.

    python scripts/backfill_newsletter_insights.py            # dry run
    python scripts/backfill_newsletter_insights.py --apply
    python scripts/backfill_newsletter_insights.py --apply --limit 20
"""
from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import db_utils
from newsletter_ingestor import (
    chunk_text,
    extract_newsletter_insights,
    is_promo_only,
    mark_promo_only,
    store_newsletter_insights,
)

# Matches _NEWSLETTER_WORKERS in api.py. The agent-server proxy is the bottleneck,
# not the DB — the session pooler tolerates far more than this (db_utils.DB_POOL_MAX).
WORKERS = 4

SELECT_BACKLOG = """
    SELECT n.id, n.source, n.subject, n.body_text
    FROM newsletters n
    WHERE n.body_text IS NOT NULL
      AND length(n.body_text) >= 100
      AND NOT n.promo_only
      AND NOT n.processed
      AND NOT EXISTS (
          SELECT 1 FROM newsletter_insights ni WHERE ni.newsletter_id = n.id
      )
    ORDER BY n.published_at DESC
    LIMIT %s
"""

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def fetch_backlog(limit: int) -> list[tuple]:
    conn = db_utils.connect(sslmode="require")
    try:
        with conn.cursor() as cur:
            cur.execute(SELECT_BACKLOG, (limit,))
            return cur.fetchall()
    finally:
        conn.close()


def process_one(row: tuple) -> tuple[str, int, str | None]:
    """Extract + store one newsletter. Returns (subject, insight_count, error)."""
    nl_id, source, subject, body_text = str(row[0]), row[1], row[2] or "", row[3]
    try:
        # Gate before extraction so a registration blast costs one small classifier
        # call instead of a full multi-chunk pass, and lands no junk insights.
        if is_promo_only(body_text, subject):
            mark_promo_only(nl_id)
            return subject, 0, None  # counted as handled, not failed
        insights: list[dict] = []
        for chunk in chunk_text(body_text):
            got = extract_newsletter_insights(chunk)
            for ins in got:
                ins["source_chunk"] = chunk[:500]
            insights.extend(got)
        # A zero-insight result is a real outcome for thin/promo issues, but storing
        # it would mark the row processed and hide it from this backlog query
        # forever. Leave it unprocessed and report it instead — the promo gate
        # (Phase 4) is what should be classifying these, not a silent empty write.
        if not insights:
            return subject, 0, "extraction returned 0 insights (left unprocessed)"
        store_newsletter_insights(nl_id, source, insights)
        return subject, len(insights), None
    except Exception as e:  # noqa: BLE001 — one bad issue must not kill the run
        return subject, 0, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to DB (default is dry run)")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    rows = fetch_backlog(args.limit)
    print(f"newsletters lacking insights: {len(rows)}")
    if not rows:
        print("nothing to do")
        return 0

    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r[1]] = by_source.get(r[1], 0) + 1
    print("by source: " + ", ".join(f"{k}={v}" for k, v in sorted(by_source.items())))

    if not args.apply:
        print("\n-- DRY RUN — no writes. Sample of what would be extracted:")
        for r in rows[:10]:
            print(f"   [{r[1]}] {(r[2] or '')[:70]}  ({len(r[3])} chars)")
        print(f"\nre-run with --apply to process all {len(rows)}")
        return 0

    ok = failed = promo = total_insights = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(process_one, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            subject, count, err = fut.result()
            if err:
                failed += 1
                _log(f"[{i}/{len(rows)}] FAIL {subject[:55]} — {err}")
            elif count == 0:
                promo += 1
                _log(f"[{i}/{len(rows)}] promo {subject[:55]} — skipped, no extraction")
            else:
                ok += 1
                total_insights += count
                _log(f"[{i}/{len(rows)}] ok   {subject[:55]} — {count} insights")

    print(f"\ndone: {ok} extracted ({total_insights} insights), "
          f"{promo} promo-skipped, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
