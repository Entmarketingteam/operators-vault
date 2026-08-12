#!/usr/bin/env python3
"""Backfill `embedding` (halfvec(512), text-embedding-3-small) on insights and
newsletter_insights rows where embedding IS NULL.

Naturally resumable: re-running just re-queries WHERE embedding IS NULL, so a
kill/restart continues where it left off with no separate checkpoint table.

Usage:
    python scripts/backfill_embeddings.py                # both tables, full backfill
    python scripts/backfill_embeddings.py --table insights
    python scripts/backfill_embeddings.py --batch-size 200
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
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

import db_utils

MODEL = "text-embedding-3-small"
DIMENSIONS = 512
TABLES = ("insights", "newsletter_insights")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_embeddings")


def _ensure_openai_key() -> None:
    if os.environ.get("OPENAI_API_KEY"):
        return
    result = subprocess.run(
        ["doppler", "secrets", "get", "OPENAI_API_KEY", "--project", "ent-agency-automation",
         "--config", "dev", "--plain"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Could not fetch OPENAI_API_KEY from Doppler: {result.stderr.strip()}")
    os.environ["OPENAI_API_KEY"] = result.stdout.strip()


def _embed_text(title: str | None, description: str | None) -> str:
    title = (title or "").strip()
    description = (description or "").strip()
    return f"{title}. {description}".strip(". ").strip()


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in values) + "]"


def backfill_table(client, conn, table: str, batch_size: int) -> tuple[int, int]:
    """Returns (rows_embedded, total_tokens_used)."""
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) FROM {table} WHERE embedding IS NULL")
    remaining = cur.fetchone()[0]
    log.info("table=%s remaining=%d", table, remaining)

    done = 0
    total_tokens = 0
    while True:
        cur.execute(
            f"""
            SELECT id, title, description FROM {table}
            WHERE embedding IS NULL
            ORDER BY id
            LIMIT %s
            """,
            (batch_size,),
        )
        rows = cur.fetchall()
        if not rows:
            break

        ids: list[str] = []
        texts: list[str] = []
        empty_ids: list[str] = []
        for row_id, title, description in rows:
            text = _embed_text(title, description)
            if not text:
                empty_ids.append(row_id)
                continue
            ids.append(row_id)
            texts.append(text)

        if empty_ids:
            # Nothing to embed (both title and description empty) — mark with a
            # zero vector so the WHERE embedding IS NULL query stops re-selecting
            # these rows forever.
            zero_literal = _vector_literal([0.0] * DIMENSIONS)
            cur.executemany(
                f"UPDATE {table} SET embedding = %s WHERE id = %s",
                [(zero_literal, rid) for rid in empty_ids],
            )
            conn.commit()
            log.info("table=%s skipped %d rows with empty title+description", table, len(empty_ids))

        if texts:
            resp = client.embeddings.create(model=MODEL, dimensions=DIMENSIONS, input=texts)
            total_tokens += getattr(resp.usage, "total_tokens", 0)
            updates = [
                (_vector_literal(item.embedding), rid)
                for item, rid in zip(resp.data, ids)
            ]
            cur.executemany(f"UPDATE {table} SET embedding = %s WHERE id = %s", updates)
            conn.commit()

        done += len(rows)
        log.info("table=%s progress=%d/%d", table, done, remaining)

    return done, total_tokens


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", choices=TABLES, help="Only backfill this table")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    _ensure_openai_key()
    from openai import OpenAI
    client = OpenAI()

    db_url = db_utils.resolve_db_url()
    conn = db_utils.connect(db_url)

    tables = (args.table,) if args.table else TABLES
    grand_total_tokens = 0
    start = time.time()
    for table in tables:
        done, tokens = backfill_table(client, conn, table, args.batch_size)
        grand_total_tokens += tokens
        log.info("table=%s done=%d tokens=%d", table, done, tokens)

    conn.close()
    elapsed = time.time() - start
    est_cost = grand_total_tokens / 1_000_000 * 0.02
    log.info("all done in %.1fs, total_tokens=%d, est_cost=$%.4f", elapsed, grand_total_tokens, est_cost)


if __name__ == "__main__":
    main()
