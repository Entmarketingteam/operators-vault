"""
Remove Meilisearch vars and set SUPABASE_JWT_SECRET (and optional Supabase vars) on Railway.
Requires: RAILWAY_API_TOKEN in .env. For JWT: add SUPABASE_JWT_SECRET from Supabase → Settings → API → JWT secret.
Uses Railway GraphQL API. Run from repo root after `railway link` (or set RAILWAY_PROJECT_ID, etc.).
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
    p = os.environ.get("RAILWAY_PROJECT_ID")
    e = os.environ.get("RAILWAY_ENVIRONMENT_ID")
    s = os.environ.get("RAILWAY_SERVICE_ID")
    if p and e and s:
        return (p, e, s)
    cfg = Path.home() / ".railway" / "config.json"
    if not cfg.exists():
        return None
    data = json.loads(cfg.read_text(encoding="utf-8"))
    projs = data.get("projects") or {}
    key = str(ROOT)
    if key in projs:
        rec = projs[key]
        return (rec["project"], rec["environment"], rec["service"])
    for k, v in projs.items():
        if "operators-vault" in k.replace("\\", "/") or "operators-vault" in k:
            return (v["project"], v["environment"], v["service"])
    return None


def main() -> int:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN missing in .env", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print(
            "Could not get project/environment/service. Run: railway link",
            file=sys.stderr,
        )
        return 1
    project_id, environment_id, service_id = ids

    import httpx

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 1) Delete Meilisearch variables
    for var_name in ("MEILISEARCH_HOST", "MEILISEARCH_API_KEY"):
        try:
            r = httpx.post(
                RAILWAY_GRAPHQL,
                json={
                    "query": """
                    mutation variableDelete($input: VariableDeleteInput!) {
                      variableDelete(input: $input)
                    }
                    """,
                    "variables": {
                        "input": {
                            "projectId": project_id,
                            "environmentId": environment_id,
                            "serviceId": service_id,
                            "name": var_name,
                        }
                    },
                },
                headers=headers,
                timeout=30.0,
            )
            r.raise_for_status()
            out = r.json()
            if out.get("errors"):
                # Variable might not exist
                print(f"Note: {var_name} - {out['errors']}", file=sys.stderr)
            else:
                print(f"Removed {var_name} from Railway.")
        except httpx.HTTPError as e:
            print(f"Warning: could not delete {var_name}: {e}", file=sys.stderr)

    # 2) Set SUPABASE_JWT_SECRET if present in .env
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if jwt_secret and "your-" not in jwt_secret.lower() and not (jwt_secret.startswith("<") and jwt_secret.endswith(">")):
        try:
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
                            "serviceId": service_id,
                            "variables": {"SUPABASE_JWT_SECRET": jwt_secret},
                        }
                    },
                },
                headers=headers,
                timeout=30.0,
            )
            r.raise_for_status()
            out = r.json()
            if out.get("errors"):
                print("Railway API errors:", out["errors"], file=sys.stderr)
                return 1
            print("Set SUPABASE_JWT_SECRET on Railway.")
        except httpx.HTTPError as e:
            print("Failed to set SUPABASE_JWT_SECRET:", e, file=sys.stderr)
            return 1
    else:
        print(
            "SUPABASE_JWT_SECRET not in .env or placeholder. Add it from Supabase → Settings → API → JWT secret, then re-run this script.",
            file=sys.stderr,
        )

    print("Done. Redeploy the service if needed (or wait for auto-deploy).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
