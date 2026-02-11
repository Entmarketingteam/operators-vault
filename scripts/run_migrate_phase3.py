"""
Run sql/migrate_phase3_visuals.sql (visual moments table and search).
Requires DATABASE_URL. Safe to run multiple times.
Usage: python scripts/run_migrate_phase3.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_env = ROOT / ".env"
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


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set. Add it to .env.", file=sys.stderr)
        return 1
    path = ROOT / "sql" / "migrate_phase3_visuals.sql"
    if not path.exists():
        print(f"Migration not found: {path}", file=sys.stderr)
        return 1
    sql = path.read_text(encoding="utf-8")
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 required. pip install psycopg2-binary", file=sys.stderr)
        return 1

    statements = [
        s.strip() for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in statements:
            if stmt:
                cur.execute(stmt + ";" if not stmt.rstrip().endswith(";") else stmt)
        cur.close()
        conn.close()
        print("Phase 3 migration (Visual moments) applied successfully.")
        return 0
    except Exception as e:
        print(f"Error applying migration: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
