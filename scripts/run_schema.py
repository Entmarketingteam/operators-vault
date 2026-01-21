"""
Run sql/schema.sql against the database. Requires DATABASE_URL in .env.
Usage: python scripts/run_schema.py
Or from project root: python -m scripts.run_schema
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
        print("DATABASE_URL not set. Add it to .env (from Supabase → Connect → Connection string → URI).", file=sys.stderr)
        return 1
    schema_path = ROOT / "sql" / "schema.sql"
    if not schema_path.exists():
        print(f"Schema not found: {schema_path}", file=sys.stderr)
        return 1
    sql = schema_path.read_text(encoding="utf-8")
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 required. pip install psycopg2-binary", file=sys.stderr)
        return 1
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("Schema applied successfully.")
        return 0
    except Exception as e:
        print(f"Error applying schema: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
