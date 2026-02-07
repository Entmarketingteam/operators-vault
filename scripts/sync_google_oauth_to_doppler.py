"""
Push GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from .env to Doppler.
Run once after: doppler login  and  doppler setup  (in the repo root).
Or set DOPPLER_TOKEN and optionally DOPPLER_PROJECT, DOPPLER_CONFIG.
"""
from __future__ import annotations

import os
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
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def main() -> int:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be in .env", file=sys.stderr)
        return 1
    # Values with special chars must be passed safely; doppler accepts KEY=value
    cmd = [
        "doppler", "secrets", "set",
        f"GOOGLE_CLIENT_ID={client_id}",
        f"GOOGLE_CLIENT_SECRET={client_secret}",
        "--silent",
    ]
    try:
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True, timeout=30)
        print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in Doppler.")
        return 0
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip() or str(e)
        print(f"Doppler error: {err}", file=sys.stderr)
        if "token" in err.lower():
            print("Run: doppler login   then  doppler setup   in the repo root, then re-run this script.", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("Doppler CLI not found. Install: winget install Doppler.doppler", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
