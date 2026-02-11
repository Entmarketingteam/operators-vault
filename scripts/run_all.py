"""
Run phases: schema, Phase 1 migration, optional seed from CSV and/or fetch from YouTube, then process.
Usage:
  python scripts/run_all.py                    # schema + migration + fetch-new + process-new (needs YOUTUBE_API_KEY)
  python scripts/run_all.py --seed-csvs       # also seed from CSVs (incl. operators_and_titans) before fetch
  python scripts/run_all.py --csv-only        # schema + migration + seed-csvs + process-new (no YouTube API)
  python scripts/run_all.py --schema-only     # only apply schema
  python scripts/run_all.py --migration-only   # only run Phase 1 migration
"""
from __future__ import annotations

import os
import subprocess
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

# change to project root so pipeline/scripts resolve
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def _run(cmd: list[str], desc: str) -> bool:
    print(f"\n--- {desc} ---", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run schema, Phase 1 migration, seed/fetch, process-new")
    ap.add_argument("--schema", action="store_true", default=True, help="Apply schema (default: True)")
    ap.add_argument("--no-schema", action="store_true", dest="no_schema", help="Skip schema")
    ap.add_argument("--seed-csvs", action="store_true", help="Seed from CSVs (incl. operators_and_titans) before fetch-new")
    ap.add_argument("--csv-only", action="store_true", help="Skip fetch-new: only schema + migration + seed-csvs + process-new (no YOUTUBE_API_KEY needed)")
    ap.add_argument("--schema-only", action="store_true", help="Only run schema, then exit")
    ap.add_argument("--migration-only", action="store_true", help="Only run Phase 1 migration, then exit")
    args = ap.parse_args()

    do_schema = args.schema and not args.no_schema

    if do_schema:
        if not _run([sys.executable, "scripts/run_schema.py"], "Schema"):
            return 1
        if args.schema_only:
            return 0

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL not set. Add it to .env (Supabase connection string).", file=sys.stderr)
        if not args.migration_only:
            return 1
    else:
        if not _run([sys.executable, "scripts/run_migrate_phase1.py"], "Phase 1 migration (YouTube stats + TITANS)"):
            return 1
    if args.migration_only:
        return 0

    if args.seed_csvs or args.csv_only:
        if not os.environ.get("DATABASE_URL"):
            print("DATABASE_URL not set; skipping seed-csvs.", file=sys.stderr)
        elif not _run([sys.executable, "pipeline.py", "--seed-csvs"], "Seed from CSVs"):
            return 1

    if args.csv_only:
        if not os.environ.get("DATABASE_URL"):
            return 1
        if not _run([sys.executable, "pipeline.py", "--process-new"], "Process new (transcribe + extract)"):
            return 1
        print("\n--- Done (csv-only) ---", flush=True)
        return 0

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL not set; cannot fetch-new/process-new.", file=sys.stderr)
        return 1
    if not os.environ.get("YOUTUBE_API_KEY"):
        print("YOUTUBE_API_KEY not set; cannot fetch-new.", file=sys.stderr)
        return 1

    if not _run([sys.executable, "pipeline.py", "--fetch-new"], "Fetch new from YouTube"):
        return 1
    if not _run([sys.executable, "pipeline.py", "--process-new"], "Process new (transcribe + extract)"):
        return 1

    print("\n--- Done ---", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
