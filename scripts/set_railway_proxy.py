"""
Set YT_DLP_PROXY (and optionally other env vars) on the operators-vault Railway service.

Requires: RAILWAY_API_TOKEN env var or passed as argument.
Finds the operators-vault project automatically via Railway API.

Usage:
    RAILWAY_API_TOKEN=<token> python scripts/set_railway_proxy.py <proxy_url>
    python scripts/set_railway_proxy.py --token <railway_token> <proxy_url>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

RAILWAY_GRAPHQL = "https://backboard.railway.app/graphql/v2"
RAILWAY_APP_DOMAIN = "superb-smile-production.up.railway.app"


def _gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = Request(
        RAILWAY_GRAPHQL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp = urlopen(req, timeout=30)
    return json.loads(resp.read())


def find_operators_vault_project(token: str) -> tuple[str, str, str] | None:
    """Find the operators-vault project, environment, and service IDs."""
    result = _gql(token, "{ me { projects { edges { node { id name services { edges { node { id name } } } environments { edges { node { id name } } } } } } } }")
    if result.get("errors"):
        print(f"API error: {result['errors']}", file=sys.stderr)
        return None

    projects = result.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])
    for edge in projects:
        proj = edge["node"]
        # Match by known domain or name
        name = (proj.get("name") or "").lower()
        if "operator" in name or "vault" in name or "superb-smile" in name:
            proj_id = proj["id"]
            # Get production environment
            envs = proj.get("environments", {}).get("edges", [])
            env_id = None
            for e in envs:
                env_name = (e["node"].get("name") or "").lower()
                if "prod" in env_name:
                    env_id = e["node"]["id"]
                    break
            if not env_id and envs:
                env_id = envs[0]["node"]["id"]

            # Get first service
            services = proj.get("services", {}).get("edges", [])
            svc_id = services[0]["node"]["id"] if services else None

            if env_id and svc_id:
                print(f"Found project: {proj.get('name')} (id={proj_id})")
                return (proj_id, env_id, svc_id)

    return None


def set_variables(token: str, project_id: str, environment_id: str, service_id: str, variables: dict) -> bool:
    query = """
    mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
      variableCollectionUpsert(input: $input)
    }
    """
    gql_vars = {
        "input": {
            "projectId": project_id,
            "environmentId": environment_id,
            "serviceId": service_id,
            "variables": variables,
        }
    }
    result = _gql(token, query, gql_vars)
    if result.get("errors"):
        print(f"Error setting variables: {result['errors']}", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Set YT_DLP_PROXY on Railway")
    parser.add_argument("proxy_url", help="Proxy URL (e.g. http://user:pass@proxy.webshare.io:80)")
    parser.add_argument("--token", default=os.environ.get("RAILWAY_API_TOKEN", ""), help="Railway API token")
    args = parser.parse_args()

    token = args.token.strip()
    if not token:
        print("RAILWAY_API_TOKEN required. Generate at https://railway.com/account/tokens", file=sys.stderr)
        return 1

    proxy_url = args.proxy_url.strip()
    if not proxy_url:
        print("Proxy URL required", file=sys.stderr)
        return 1

    print("Finding operators-vault project on Railway...")
    ids = find_operators_vault_project(token)
    if not ids:
        print("Could not find operators-vault project. Check token permissions.", file=sys.stderr)
        return 1

    project_id, env_id, svc_id = ids
    print(f"Setting YT_DLP_PROXY on service...")

    if set_variables(token, project_id, env_id, svc_id, {"YT_DLP_PROXY": proxy_url}):
        print(f"Done! YT_DLP_PROXY set. Railway will auto-redeploy.")
        print(f"Verify at: https://{RAILWAY_APP_DOMAIN}/health")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
