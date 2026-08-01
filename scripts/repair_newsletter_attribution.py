#!/usr/bin/env python3
"""Re-derive `newsletters.source` from the real Gmail From header.

Why this exists
---------------
The n8n "Newsletter Daily Sync" (wf FPWjPuFq2jkPkJmj) Parse Email Body node read
its source with `$('Source Config').first().json`. `.first()` always returns
config item #1 — nik_sharma — so every newsletter ingested since ~2026-05-09 was
filed as Nik Sharma regardless of who actually sent it. Verified: Taylor Holiday's
"Turn your inventory into Q4 cash" and Matt Bertulli's "planning vs. execution"
are both stored as nik_sharma.

The From header is the only authority here (verification-law L5 — contradictions
are resolved by the artifact), so this script maps email_id -> real sender using
data pulled from the Gmail API, then rewrites `newsletters.source`/`author` and
`newsletter_insights.source` in lockstep. Rows whose Gmail message no longer
exists are quarantined as 'unclassified', never deleted or guessed (traps.md T4).

Input is a TSV of `<gmail_message_id>\t<sender_email>` produced from the Gmail API.

    python scripts/repair_newsletter_attribution.py --map /path/sender_map.tsv
    python scripts/repair_newsletter_attribution.py --map /path/sender_map.tsv --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import db_utils
from newsletter_ingestor import NEWSLETTER_SOURCES, infer_source_from_sender

# The attribution bug shipped ~2026-05-09; scope the repair to rows it could touch.
CORRUPTION_START = "2026-05-01"
QUARANTINE_SLUG = "unclassified"


def load_map(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[0]:
                out[parts[0]] = parts[1].strip().lower()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="TSV: gmail_message_id<TAB>sender_email")
    ap.add_argument("--apply", action="store_true", help="write (default is dry run)")
    args = ap.parse_args()

    sender_by_id = load_map(args.map)
    print(f"sender map entries: {len(sender_by_id)}")

    conn = db_utils.connect(sslmode="require")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, email_id, source, subject, published_at::date
        FROM newsletters
        WHERE source = 'nik_sharma' AND published_at >= %s
        ORDER BY published_at DESC
        """,
        (CORRUPTION_START,),
    )
    rows = cur.fetchall()
    print(f"rows in corruption window (source=nik_sharma, >= {CORRUPTION_START}): {len(rows)}\n")

    planned: list[tuple] = []   # (nl_id, new_slug, new_author, subject, date, old_slug)
    quarantine: list[tuple] = []
    unchanged = 0

    for nl_id, email_id, old_slug, subject, pub in rows:
        sender = sender_by_id.get(email_id)
        if not sender:
            quarantine.append((nl_id, subject, pub))
            continue
        new_slug = infer_source_from_sender(sender)
        if not new_slug:
            quarantine.append((nl_id, subject, pub))
            continue
        if new_slug == old_slug:
            unchanged += 1
            continue
        planned.append((nl_id, new_slug, NEWSLETTER_SOURCES[new_slug]["author"], subject, pub, old_slug))

    moves = Counter(f"{p[5]} -> {p[1]}" for p in planned)
    print(f"correctly attributed already : {unchanged}")
    print(f"to be re-attributed          : {len(planned)}")
    for k, v in moves.most_common():
        print(f"    {k}: {v}")
    print(f"to be quarantined ({QUARANTINE_SLUG}) : {len(quarantine)}")

    if planned:
        print("\nsample of re-attributions:")
        for nl_id, slug, author, subject, pub, old in planned[:12]:
            print(f"   {pub}  {old} -> {slug:22s} {(subject or '')[:52]}")
    if quarantine:
        print("\nquarantined (Gmail message gone — never guessed):")
        for nl_id, subject, pub in quarantine:
            print(f"   {pub}  {(subject or '')[:60]}")

    if not args.apply:
        print("\n-- DRY RUN — no writes. Re-run with --apply.")
        return 0

    updated_nl = updated_ins = 0
    for nl_id, slug, author, _subject, _pub, _old in planned:
        cur.execute(
            "UPDATE newsletters SET source = %s, author = %s WHERE id = %s",
            (slug, author, nl_id),
        )
        updated_nl += cur.rowcount
        # newsletter_insights carries its own denormalised `source`; it must move
        # with the parent or search filters and the Discover source breakdown lie.
        cur.execute(
            "UPDATE newsletter_insights SET source = %s WHERE newsletter_id = %s",
            (slug, nl_id),
        )
        updated_ins += cur.rowcount

    for nl_id, _subject, _pub in quarantine:
        cur.execute(
            "UPDATE newsletters SET source = %s WHERE id = %s", (QUARANTINE_SLUG, nl_id)
        )
        cur.execute(
            "UPDATE newsletter_insights SET source = %s WHERE newsletter_id = %s",
            (QUARANTINE_SLUG, nl_id),
        )

    conn.commit()
    print(f"\napplied: {updated_nl} newsletters, {updated_ins} newsletter_insights, "
          f"{len(quarantine)} quarantined")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
