"""
Create the Operators Vault cron service on Railway via API.
Creates a new service that runs curl to /trigger-sync on a schedule (every 3 hours).
Requires: RAILWAY_API_TOKEN in .env. Run 'railway link' in repo root first (or set RAILWAY_PROJECT_ID, RAILWAY_ENVIRONMENT_ID).
Usage: python scripts/create_railway_cron_service.py
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
CRON_SCHEDULE = "0 */3 * * *"  # Every 3 hours
TRIGGER_URL_DEFAULT = "https://superb-smile-production.up.railway.app/trigger-sync"


def _load_railway_ids() -> tuple[str, str, str | None] | None:
    """Returns (project_id, environment_id, main_service_id)."""
    p = os.environ.get("RAILWAY_PROJECT_ID")
    e = os.environ.get("RAILWAY_ENVIRONMENT_ID")
    s = os.environ.get("RAILWAY_SERVICE_ID")
    if p and e:
        return (p, e, s)
    cfg = Path.home() / ".railway" / "config.json"
    if not cfg.exists():
        return None
    data = json.loads(cfg.read_text(encoding="utf-8"))
    projs = data.get("projects") or {}
    for k, v in projs.items():
        if "operators-vault" in k.replace("\\", "/") or "operators-vault" in str(k):
            return (v["project"], v["environment"], v.get("service"))
    # Use first project if single
    for k, v in projs.items():
        return (v["project"], v["environment"], v.get("service"))
    return None


def main() -> int:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN required. Add to .env from Railway Account -> Tokens", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print("Run 'railway link' in the repo root, or set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID", file=sys.stderr)
        return 1

    project_id, environment_id, main_service_id = ids
    trigger_url = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/") + "/trigger-sync"
    
    # Try to get SYNC_TRIGGER_KEY from Railway main service variables
    sync_key = os.environ.get("SYNC_TRIGGER_KEY", "").strip()
    if not sync_key and main_service_id:
        # Query Railway for the main service's SYNC_TRIGGER_KEY variable
        try:
            import httpx
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            r = httpx.post(
                RAILWAY_GRAPHQL,
                json={
                    "query": """
                    query variables($projectId: String!, $environmentId: String!, $serviceId: String!) {
                      variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) {
                        name
                        value
                      }
                    }
                    """,
                    "variables": {
                        "projectId": project_id,
                        "environmentId": environment_id,
                        "serviceId": main_service_id,
                    },
                },
                headers=headers,
                timeout=30.0,
            )
            if r.status_code == 200:
                out = r.json()
                if not out.get("errors") and out.get("data"):
                    vars_list = out["data"].get("variables") or []
                    for var in vars_list:
                        if var.get("name") == "SYNC_TRIGGER_KEY":
                            sync_key = var.get("value", "").strip()
                            print(f"Found SYNC_TRIGGER_KEY from Railway main service.")
                            break
        except Exception as e:
            print(f"Note: Could not query Railway for SYNC_TRIGGER_KEY: {e}", file=sys.stderr)
            print("Set SYNC_TRIGGER_KEY in .env to match Railway, or the cron will call without key.", file=sys.stderr)
    
    if sync_key:
        trigger_url += f"?key={sync_key}"
    else:
        print("Warning: SYNC_TRIGGER_KEY not found. Cron will call /trigger-sync without key.", file=sys.stderr)
        print("If your Railway service requires SYNC_TRIGGER_KEY, set it in .env and rerun this script.", file=sys.stderr)

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1) Create service from Docker image
    print("Creating cron service (Docker image: curlimages/curl)...")
    r = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation serviceCreate($input: ServiceCreateInput!) {
              serviceCreate(input: $input) {
                id
                name
              }
            }
            """,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "name": "vault-sync-cron",
                    "source": {
                        "image": "curlimages/curl:latest",
                    },
                }
            },
        },
        headers=headers,
        timeout=30.0,
    )
    if r.status_code != 200:
        print(f"API error {r.status_code}: {r.text}", file=sys.stderr)
        return 1
    out = r.json()
    if out.get("errors"):
        err = out["errors"]
        print(f"GraphQL errors: {err}", file=sys.stderr)
        # Try empty service if Docker create fails
        if "image" in str(err).lower() or "source" in str(err).lower():
            print("Tip: Create the cron service manually: Railway → New → Empty Service, then set Cron Schedule and Start Command.", file=sys.stderr)
        return 1
    data = out.get("data") or {}
    service = data.get("serviceCreate") or {}
    service_id = service.get("id")
    if not service_id:
        print("No service ID returned", file=sys.stderr)
        return 1
    print(f"Created service: {service.get('name')} (id={service_id})")

    # 2) Set variable TRIGGER_URL
    print("Setting TRIGGER_URL variable...")
    r2 = httpx.post(
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
                    "serviceId": service_id,
                    "variables": {"TRIGGER_URL": trigger_url},
                }
            },
        },
        headers=headers,
        timeout=30.0,
    )
    if r2.status_code == 200 and not (r2.json().get("errors")):
        print("Set TRIGGER_URL.")
    else:
        print(f"Variable set warning: {r2.text}", file=sys.stderr)

    # 3) Update service instance: start command + cron schedule (serviceId/environmentId are top-level args)
    print("Setting start command and cron schedule...")
    r3 = httpx.post(
        RAILWAY_GRAPHQL,
        json={
            "query": """
            mutation serviceInstanceUpdate($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
              serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
            }
            """,
            "variables": {
                "serviceId": service_id,
                "environmentId": environment_id,
                "input": {
                    "startCommand": "curl -sS -X GET \"$TRIGGER_URL\"",
                    "cronSchedule": CRON_SCHEDULE,
                }
            },
        },
        headers=headers,
        timeout=30.0,
    )
    if r3.status_code != 200:
        print(f"Update warning {r3.status_code}: {r3.text}", file=sys.stderr)
    else:
        j = r3.json()
        if j.get("errors"):
            print(f"Update errors: {j['errors']}", file=sys.stderr)
            print("Manually set in Railway: Service → Settings → Cron Schedule = 0 */3 * * *", file=sys.stderr)
        else:
            print(f"Cron schedule set to: {CRON_SCHEDULE} (every 3 hours)")

    print("Done. Cron service will call trigger-sync every 3 hours.")
    print("Check Railway Dashboard -> vault-sync-cron -> Logs after the first run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
