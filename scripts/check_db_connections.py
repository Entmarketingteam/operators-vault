#!/usr/bin/env python3
"""
Ratchet-based guardrail for Postgres connection sprawl.

Policy: all Postgres connections must go through db.connect(), which applies
statement_timeout, TCP keepalives, and connect_timeout. Direct calls to
psycopg2.connect() are legacy and MUST NOT INCREASE.

How it works:
  - Scans every *.py file in the repo (except db.py itself, which is the
    one place direct psycopg2.connect() is allowed).
  - Counts direct `psycopg2.connect(` call sites.
  - Compares against BASELINE below.
  - Fails CI if the count goes UP.
  - Prints a reminder to decrement BASELINE if the count goes DOWN.

Migrating a call site:
  Before:  conn = psycopg2.connect(db_url, connect_timeout=10)
  After:   from db import connect; conn = connect(db_url)
  Then decrement BASELINE below by the number of call sites you migrated
  and commit the decrement in the same PR.

Why ratchet instead of strict ban: we have ~65 legacy call sites. A strict
ban would force a 65-file refactor in one PR, which is risky. The ratchet
lets us pay the debt down incrementally while guaranteeing we never add new
direct calls.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Current count of direct psycopg2.connect() calls outside db.py.
# DECREMENT this number when you migrate a call site to db.connect().
# Never increment — new code must use db.connect().
BASELINE = 61

# Files/directories to skip
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "frontend"}
# db.py is the one authorised home for psycopg2.connect()
ALLOWED_FILES = {"db.py"}

PATTERN = re.compile(r"psycopg2\.connect\(")


def find_call_sites(root: Path) -> list[tuple[Path, int, str]]:
    """Return list of (path, line_number, line_text) for each call site."""
    hits: list[tuple[Path, int, str]] = []
    for py in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py.parts):
            continue
        if py.name in ALLOWED_FILES:
            continue
        # Skip this script itself — it contains the pattern as a string
        if py.resolve() == Path(__file__).resolve():
            continue
        try:
            for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                # Ignore commented-out lines
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if PATTERN.search(line):
                    hits.append((py, i, line.strip()))
        except (UnicodeDecodeError, OSError):
            continue
    return hits


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    hits = find_call_sites(root)
    count = len(hits)

    print(f"Direct psycopg2.connect() call sites: {count} (baseline: {BASELINE})")

    if count > BASELINE:
        print()
        print(f"ERROR: {count - BASELINE} new direct psycopg2.connect() call(s) detected.")
        print("       New code must use db.connect() from db.py.")
        print()
        print("Call sites:")
        for path, lineno, text in hits:
            rel = path.relative_to(root)
            print(f"  {rel}:{lineno}  {text}")
        return 1

    if count < BASELINE:
        print()
        print(f"NOTE: count is below baseline. Decrement BASELINE in "
              f"{Path(__file__).name} from {BASELINE} to {count} "
              "to lock in the progress.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
