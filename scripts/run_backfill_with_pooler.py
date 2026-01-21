"""
Run pipeline --seed-csvs --process-all. If DATABASE_URL uses Supabase Direct
(db.*.supabase.co) and that host is unreachable, rewrites to Session pooler
(aws-0-us-west-2.pooler.supabase.com) and retries.
Requires: .env with DATABASE_URL; CSVs in %USERPROFILE%\\Downloads\\.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

# Session pooler (Railway uses this). Region from HANDOFF: aws-0-us-west-2.
POOLER_HOST = "aws-0-us-west-2.pooler.supabase.com"
POOLER_PORT = "5432"


def _parse_pg_url(url: str) -> dict | None:
    """Parse postgresql://user:pass@host:port/db into components. Returns None if not postgres."""
    if not url or "postgresql" not in url and "postgres" not in url:
        return None
    s = url.strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    if "@" not in s:
        return None
    auth, rest = s.rsplit("@", 1)
    if ":" not in auth:
        return None
    user, password = auth.split(":", 1)
    if "/" in rest:
        hostport, dbname = rest.split("/", 1)
        dbname = dbname.split("?")[0] or "postgres"
    else:
        hostport, dbname = rest, "postgres"
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, "5432"
    return {"user": user, "password": password, "host": host, "port": port, "dbname": dbname}


def _is_direct_supabase(host: str) -> bool:
    return bool(host and "db." in host and "supabase.co" in host and "pooler" not in host)


def _project_ref_from_host(host: str) -> str | None:
    m = re.search(r"db\.([^.]+)\.supabase\.co", host or "")
    return m.group(1) if m else None


def _to_pooler_url(parsed: dict) -> str:
    """Build Session pooler URL. User must be postgres.[project-ref]."""
    ref = _project_ref_from_host(parsed["host"])
    if not ref:
        return ""
    user = f"postgres.{ref}"
    return f"postgresql://{user}:{parsed['password']}@{POOLER_HOST}:{POOLER_PORT}/{parsed['dbname']}"


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL not set in .env", file=sys.stderr)
        return 1

    env = os.environ.copy()
    parsed = _parse_pg_url(db_url)
    if parsed and _is_direct_supabase(parsed["host"]):
        pooler = _to_pooler_url(parsed)
        if pooler:
            print("DATABASE_URL is Supabase Direct; using Session pooler for reachability.", flush=True)
            env["DATABASE_URL"] = pooler

    cmd = [sys.executable, str(ROOT / "pipeline.py"), "--seed-csvs", "--process-all"]
    r = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
