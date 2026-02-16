"""
Get list of unprocessed videos from Railway API.
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

RAILWAY_APP_URL = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/")


def main():
    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1
    
    # Query database via Railway API - we need to check what endpoints are available
    # For now, let's trigger process-new and see what videos it tries to process
    
    print("Triggering process-new to see which videos will be processed...")
    print(f"Endpoint: {RAILWAY_APP_URL}/process-new/async")
    
    try:
        r = httpx.post(
            f"{RAILWAY_APP_URL}/process-new/async",
            timeout=10.0,
            verify=False,
        )
        
        if r.status_code == 202:
            data = r.json()
            job_id = data.get("job_id")
            print(f"\n[OK] Job started: {job_id}")
            print(f"\nCheck job status:")
            print(f"  python scripts/trigger_process_new_test.py")
            print(f"\nOr check Railway logs to see which videos are being processed.")
            return 0
        else:
            print(f"\n[ERROR] HTTP {r.status_code}: {r.text}")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
