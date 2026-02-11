"""
Run a script with Doppler-injected env (so you don't type 'doppler run --' every time).
Requires: doppler login, doppler setup in repo root.

Usage:
  python scripts/run_with_doppler.py run_all [--csv-only] [--seed-csvs] [--migration-only] ...
  python scripts/run_with_doppler.py migrate
  python scripts/run_with_doppler.py run_all --csv-only
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print("Usage: python scripts/run_with_doppler.py <command> [args...]", file=sys.stderr)
        print("  run_all [--csv-only] [--seed-csvs] [--migration-only] ...", file=sys.stderr)
        print("  migrate", file=sys.stderr)
        return 1

    cmd_name = argv[0].lower()
    rest = argv[1:]

    if cmd_name == "migrate":
        cmd = [sys.executable, str(ROOT / "scripts" / "run_migrate_phase1.py")]
    elif cmd_name == "run_all":
        cmd = [sys.executable, str(ROOT / "scripts" / "run_all.py")] + rest
    else:
        print(f"Unknown command: {cmd_name}. Use 'run_all' or 'migrate'.", file=sys.stderr)
        return 1

    # doppler run -- python ...
    full = ["doppler", "run", "--"] + cmd
    try:
        r = subprocess.run(full, cwd=ROOT)
        return r.returncode
    except FileNotFoundError:
        print("Doppler CLI not found. Install: winget install Doppler.doppler", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
