"""
Find the existing vault-sync-cron service in the project, then set TRIGGER_URL
and cron command so it works. Use when the cron service exists but you don't
see it or it's misconfigured.
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
CRON_SCHEDULE = "0 */3 * * *"


def _load_railway_ids() -> tuple[str, str] | None:
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
        print("RAILWAY_API_TOKEN required", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print("Run 'railway link' or set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID", file=sys.stderr)
        return 1

    project_id, environment_id = ids

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # List services in project to find vault-sync-cron
    r = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            query project($id: String!) {
              project(id: $id) {
                name
                services {
                  edges {
                    node {
                      id
                      name
                    }
                  }
                }
              }
            }
            """,
            "variables": {"id": project_id},
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
        return 1

    edges = (data.get("data") or {}).get("project") or {}
    edges = (edges.get("services") or {}).get("edges") or []
    cron_id = None
    for edge in edges:
        node = edge.get("node") or {}
        if (node.get("name") or "").strip() == "vault-sync-cron":
            cron_id = (node.get("id") or "").strip()
            break

    if not cron_id:
        print("No service named 'vault-sync-cron' found in this project.", file=sys.stderr)
        print("Create it with: python scripts/create_railway_cron_service.py", file=sys.stderr)
        return 1

    print(f"Found vault-sync-cron: {cron_id}")
    trigger_url = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/") + "/sync/async"
    # Use literal URL in start command so cron works even if TRIGGER_URL env isn't injected at runtime
    start_cmd = f'curl -sS -X POST "{trigger_url}"'
    print(f"Setting start command (literal URL): {start_cmd}")

    # 1. Set TRIGGER_URL variable anyway (for reference)
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
                    "serviceId": cron_id,
                    "variables": {"TRIGGER_URL": trigger_url},
                }
            },
        },
        headers=headers,
        timeout=30,
    )
    if r1.status_code != 200 or r1.json().get("errors"):
        print(f"Warning: TRIGGER_URL variable: {r1.text}", file=sys.stderr)
    else:
        print("  TRIGGER_URL variable set.")

    # 2. Set start command (literal URL) and cron schedule - no $TRIGGER_URL dependency
    r2 = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation serviceInstanceUpdate($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
              serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
            }
            """,
            "variables": {
                "serviceId": cron_id,
                "environmentId": environment_id,
                "input": {
                    "startCommand": start_cmd,
                    "cronSchedule": CRON_SCHEDULE,
                },
            },
        },
        headers=headers,
        timeout=30,
    )
    if r2.status_code != 200 or r2.json().get("errors"):
        print(f"Failed to set start command/cron: {r2.text}", file=sys.stderr)
        return 1
    print(f"  Start command and cron schedule ({CRON_SCHEDULE}) set.")

    print("\nCron is configured. Update scripts with this ID if needed:")
    print(f"  CRON_SERVICE_ID = \"{cron_id}\"")
    print("Check Railway Dashboard -> operators-vault project -> vault-sync-cron (it's a separate service, not inside superb-smile).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
