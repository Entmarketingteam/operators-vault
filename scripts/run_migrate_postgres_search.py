"""
Run sql/migrate_postgres_search.sql (Postgres FTS + search functions).
Requires DATABASE_URL. Run after schema.sql. Safe to run multiple times.
Usage: python scripts/run_migrate_postgres_search.py
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
    path = ROOT / "sql" / "migrate_postgres_search.sql"
    if not path.exists():
        print(f"Migration not found: {path}", file=sys.stderr)
        return 1
    sql = path.read_text(encoding="utf-8")
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 required. pip install psycopg2-binary", file=sys.stderr)
        return 1

    def split_sql(text: str):
        """Split SQL into statements; do not split inside $$ ... $$."""
        statements = []
        current = []
        i = 0
        in_dollar = False
        while i < len(text):
            if i < len(text) - 1 and text[i : i + 2] == "$$":
                in_dollar = not in_dollar
                current.append("$$")
                i += 2
                continue
            if not in_dollar and text[i] == ";":
                stmt = "".join(current).strip()
                if stmt and not all(ln.strip().startswith("--") or not ln.strip() for ln in stmt.splitlines()):
                    statements.append(stmt)
                current = []
                i += 1
                continue
            current.append(text[i])
            i += 1
        if current:
            stmt = "".join(current).strip()
            if stmt and not all(ln.strip().startswith("--") or not ln.strip() for ln in stmt.splitlines()):
                statements.append(stmt)
        return statements

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in split_sql(sql):
            cur.execute(stmt if stmt.rstrip().endswith(";") else stmt + ";")
        cur.close()
        conn.close()
        print("Postgres search migration applied successfully.")
        return 0
    except Exception as e:
        print(f"Error applying migration: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
