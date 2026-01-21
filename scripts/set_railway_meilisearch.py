"""
Set MEILISEARCH_API_KEY and MEILISEARCH_HOST on Railway from .env.
Requires: RAILWAY_API_TOKEN, MEILISEARCH_API_KEY, MEILISEARCH_HOST in .env.
Uses Railway GraphQL API (backboard.railway.com). Reads project/environment/service
from ~/.railway/config.json for the linked project, or from env RAILWAY_PROJECT_ID, etc.
"""
from __future__ import annotations

import json
import os
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

RAILWAY_GRAPHQL = "https://backboard.railway.com/graphql/v2"

def _load_railway_ids() -> tuple[str, str, str] | None:
    # Prefer env
    p = os.environ.get("RAILWAY_PROJECT_ID")
    e = os.environ.get("RAILWAY_ENVIRONMENT_ID")
    s = os.environ.get("RAILWAY_SERVICE_ID")
    if p and e and s:
        return (p, e, s)
    # From ~/.railway/config.json
    cfg = Path.home() / ".railway" / "config.json"
    if not cfg.exists():
        return None
    data = json.loads(cfg.read_text(encoding="utf-8"))
    projs = data.get("projects") or {}
    key = str(ROOT)
    if key not in projs:
        for k, v in projs.items():
            if str(ROOT).replace("\\", "/") in k.replace("\\", "/") or k.endswith("operators-vault"):
                return (v["project"], v["environment"], v["service"])
        return None
    rec = projs[key]
    return (rec["project"], rec["environment"], rec["service"])

def main() -> int:
    api_key = os.environ.get("MEILISEARCH_API_KEY", "").strip()
    host = os.environ.get("MEILISEARCH_HOST", "").strip()
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not api_key or "your-" in api_key.lower() or (api_key.startswith("<") and api_key.endswith(">")):
        print("MEILISEARCH_API_KEY missing or placeholder in .env", file=sys.stderr)
        return 1
    if not host or "your-" in host.lower() or (host.startswith("<") and host.endswith(">")):
        print("MEILISEARCH_HOST missing or placeholder in .env", file=sys.stderr)
        return 1
    if not token:
        print("RAILWAY_API_TOKEN missing in .env", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print("Could not get project/environment/service from ~/.railway/config.json or RAILWAY_*_ID env. Run: railway link", file=sys.stderr)
        return 1
    project_id, environment_id, service_id = ids

    import httpx

    query = """
    mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
      variableCollectionUpsert(input: $input)
    }
    """
    variables = {
        "input": {
            "projectId": project_id,
            "environmentId": environment_id,
            "serviceId": service_id,
            "variables": {
                "MEILISEARCH_API_KEY": api_key,
                "MEILISEARCH_HOST": host,
            },
        }
    }
    try:
        r = httpx.post(
            RAILWAY_GRAPHQL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        r.raise_for_status()
        out = r.json()
        if out.get("errors"):
            print("Railway API errors:", out["errors"], file=sys.stderr)
            return 1
        print("Set MEILISEARCH_API_KEY and MEILISEARCH_HOST on Railway. Redeploy or wait for auto-deploy.")
        return 0
    except httpx.HTTPError as e:
        print("Railway API request failed:", e, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
