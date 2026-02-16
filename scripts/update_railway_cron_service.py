"""
Update the existing Railway cron service's TRIGGER_URL variable.
Requires: RAILWAY_API_TOKEN in .env. Run 'railway link' in repo root first.
Usage: python scripts/update_railway_cron_service.py
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


def _find_cron_service_id(token: str, project_id: str, environment_id: str) -> str | None:
    """Find the vault-sync-cron service ID."""
    try:
        import httpx
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = httpx.post(
            RAILWAY_GRAPHQL,
            json={
                "query": """
                query services($projectId: String!) {
                  project(id: $projectId) {
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
                "variables": {"projectId": project_id},
            },
            headers=headers,
            timeout=30.0,
        )
        if r.status_code == 200:
            out = r.json()
            if not out.get("errors") and out.get("data"):
                services = out["data"].get("project", {}).get("services", {}).get("edges", [])
                for edge in services:
                    service = edge.get("node", {})
                    if service.get("name") == "vault-sync-cron":
                        return service.get("id")
    except Exception as e:
        print(f"Error finding cron service: {e}", file=sys.stderr)
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
    
    # Find cron service
    cron_service_id = _find_cron_service_id(token, project_id, environment_id)
    if not cron_service_id:
        print("Could not find 'vault-sync-cron' service. Create it first with create_railway_cron_service.py", file=sys.stderr)
        return 1
    
    print(f"Found cron service: {cron_service_id}")
    
    # Build trigger URL
    trigger_url = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/") + "/trigger-sync"
    
    # Try to get SYNC_TRIGGER_KEY from Railway main service variables
    sync_key = os.environ.get("SYNC_TRIGGER_KEY", "").strip()
    if not sync_key and main_service_id:
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
    
    if sync_key:
        trigger_url += f"?key={sync_key}"
        print(f"Using TRIGGER_URL with key: {trigger_url[:50]}...")
    else:
        print(f"Using TRIGGER_URL without key: {trigger_url}")
        print("Warning: If your Railway service requires SYNC_TRIGGER_KEY, set it in .env", file=sys.stderr)

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Update TRIGGER_URL variable
    print("Updating TRIGGER_URL variable...")
    r = httpx.post(
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
                    "serviceId": cron_service_id,
                    "variables": {"TRIGGER_URL": trigger_url},
                }
            },
        },
        headers=headers,
        timeout=30.0,
    )
    if r.status_code == 200 and not (r.json().get("errors")):
        print("Successfully updated TRIGGER_URL.")
        return 0
    else:
        print(f"Error updating variable: {r.text}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
