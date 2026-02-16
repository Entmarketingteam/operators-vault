"""
Delete the vault-sync-cron service on Railway. Use this to clear a stuck cron run
or to remove the cron job so you can recreate it fresh.

After deleting, create a new cron with:
  python scripts/create_railway_cron_service.py

(create_railway_cron_service.py is updated to use POST /sync/async.)

Requires: RAILWAY_API_TOKEN
"""
from __future__ import annotations

import json
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

RAILWAY_GRAPHQL = "https://backboard.railway.com/graphql/v2"
CRON_SERVICE_ID = "21ebfe00-499d-4865-afef-37a0ebce317c"  # vault-sync-cron (update if you recreate again)


def main() -> int:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN required (e.g. from Doppler or .env)", file=sys.stderr)
        return 1

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # serviceDelete(id: String!) per Railway GraphQL schema
    r = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation DeleteCron($id: String!) {
              serviceDelete(id: $id)
            }
            """,
            "variables": {"id": CRON_SERVICE_ID},
        },
        headers=headers,
        timeout=30,
    )
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return 1
    data = r.json()
    if data.get("errors"):
        print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
        print("Delete manually: Railway Dashboard -> vault-sync-cron -> Settings -> Danger -> Remove Service", file=sys.stderr)
        return 1
    if data.get("data", {}).get("serviceDelete"):
        print("Cron service deleted successfully.")
        print("To recreate: python scripts/create_railway_cron_service.py")
        return 0
    print("Delete via API did not succeed. Delete manually:", file=sys.stderr)
    print("  1. Railway Dashboard -> operators-vault project -> vault-sync-cron", file=sys.stderr)
    print("  2. Settings -> Danger -> Remove Service", file=sys.stderr)
    print("  3. Then run: python scripts/create_railway_cron_service.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
