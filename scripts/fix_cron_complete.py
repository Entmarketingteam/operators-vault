"""
Complete fix for cron service - updates both TRIGGER_URL and start command.
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
CRON_SERVICE_ID = "77f276eb-0792-42bf-80fc-a536e0b1a2a6"
CRON_SCHEDULE = "0 */3 * * *"


def _load_railway_ids() -> tuple[str, str] | None:
    """Returns (project_id, environment_id)."""
    p = os.environ.get("RAILWAY_PROJECT_ID")
    e = os.environ.get("RAILWAY_ENVIRONMENT_ID")
    if p and e:
        return (p, e)
    cfg = Path.home() / ".railway" / "config.json"
    if not cfg.exists():
        return None
    data = json.loads(cfg.read_text(encoding="utf-8"))
    projs = data.get("projects") or {}
    for k, v in projs.items():
        if "operators-vault" in k.replace("\\", "/") or "operators-vault" in str(k):
            return (v["project"], v["environment"])
    for k, v in projs.items():
        return (v["project"], v["environment"])
    return None


def main() -> int:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN required.", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print("Run 'railway link' or set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID", file=sys.stderr)
        return 1

    project_id, environment_id = ids
    
    # Use POST /sync/async (more reliable)
    trigger_url = f"{os.environ.get('RAILWAY_APP_URL', 'https://superb-smile-production.up.railway.app').rstrip('/')}/sync/async"
    
    print(f"Fixing cron service: {CRON_SERVICE_ID}")
    print(f"Setting TRIGGER_URL: {trigger_url}")
    print(f"Setting start command: curl -sS -X POST \"$TRIGGER_URL\"")

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Update TRIGGER_URL variable
    print("\n1. Updating TRIGGER_URL variable...")
    r1 = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
              variableCollectionUpsert(input: $input)
            }
            """,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "environmentId": environment_id,
                    "serviceId": CRON_SERVICE_ID,
                    "variables": {"TRIGGER_URL": trigger_url},
                }
            },
        },
        headers=headers,
        timeout=30.0,
        verify=False,  # Corporate proxy SSL issues
    )
    if r1.status_code == 200 and not (r1.json().get("errors")):
        print("   [OK] TRIGGER_URL updated")
    else:
        print(f"   [ERROR] Failed to update TRIGGER_URL: {r1.text}", file=sys.stderr)
        return 1

    # 2. Update start command and cron schedule
    print("\n2. Updating start command and cron schedule...")
    r2 = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation serviceInstanceUpdate($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
              serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
            }
            """,
            "variables": {
                "serviceId": CRON_SERVICE_ID,
                "environmentId": environment_id,
                "input": {
                    "startCommand": "curl -sS -X POST \"$TRIGGER_URL\"",
                    "cronSchedule": CRON_SCHEDULE,
                }
            },
        },
        headers=headers,
        timeout=30.0,
        verify=False,
    )
    if r2.status_code == 200:
        j = r2.json()
        if j.get("errors"):
            print(f"   [ERROR] GraphQL errors: {j['errors']}", file=sys.stderr)
            return 1
        else:
            print("   [OK] Start command and cron schedule updated")
    else:
        print(f"   [ERROR] HTTP {r2.status_code}: {r2.text}", file=sys.stderr)
        return 1

    print("\n[SUCCESS] Cron service fully configured!")
    print(f"  - TRIGGER_URL: {trigger_url}")
    print(f"  - Start command: curl -sS -X POST \"$TRIGGER_URL\"")
    print(f"  - Schedule: {CRON_SCHEDULE} (every 3 hours)")
    print("\nNext cron run will execute automatically, or trigger manually:")
    print(f"  curl -X POST {trigger_url}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
