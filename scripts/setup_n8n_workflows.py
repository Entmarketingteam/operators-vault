"""
Import Operators Vault n8n workflows with Railway API URLs and activate the sync cron.
Uses N8N_HOST, N8N_API_KEY; RAILWAY_APP_URL (default: https://superb-smile-production.up.railway.app).
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

import urllib.error
import urllib.request

BASE = (os.environ.get("RAILWAY_APP_URL") or "https://superb-smile-production.up.railway.app").rstrip("/")
HOST = (os.environ.get("N8N_HOST") or "").rstrip("/")
KEY = os.environ.get("N8N_API_KEY")


def request(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{HOST}{path}"
    headers = {"Content-Type": "application/json", "X-N8N-API-KEY": KEY or ""}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"HTTP {e.code}: {err}") from e


def main() -> int:
    if not HOST or not KEY:
        print("N8N_HOST and N8N_API_KEY must be set.", file=sys.stderr)
        return 1

    # 1) Process workflow
    p = json.loads((ROOT / "n8n-workflow.json").read_text(encoding="utf-8"))
    for n in p.get("nodes", []):
        if n.get("type") == "n8n-nodes-base.httpRequest" and "parameters" in n:
            n["parameters"]["url"] = f"{BASE}/process"
            break
    payload = {"name": p.get("name", "Operators Vault – Process Video"), "nodes": p["nodes"], "connections": p["connections"], "settings": p.get("settings", {})}
    out = request("POST", "/api/v1/workflows", payload)
    wid1 = out.get("id") or (out.get("data") or {}).get("id")
    print(f"Imported: {payload['name']} (id={wid1})")

    # 2) Sync workflow
    s = json.loads((ROOT / "n8n-workflow-fetch-new.json").read_text(encoding="utf-8"))
    for n in s.get("nodes", []):
        if n.get("type") == "n8n-nodes-base.httpRequest" and "parameters" in n:
            n["parameters"]["url"] = f"{BASE}/sync"
            break
    payload2 = {"name": s.get("name", "Operators Vault – Sync New Episodes"), "nodes": s["nodes"], "connections": s["connections"], "settings": s.get("settings", {})}
    out2 = request("POST", "/api/v1/workflows", payload2)
    wid2 = out2.get("id") or (out2.get("data") or {}).get("id")
    print(f"Imported: {payload2['name']} (id={wid2})")

    # Activate sync workflow (cron) via dedicated endpoint
    try:
        request("POST", f"/api/v1/workflows/{wid2}/activate", {})
        print(f"Activated sync workflow (id={wid2})")
    except Exception as e:
        # try /rest/ if /api/v1/ does not support activate
        try:
            request("POST", f"/rest/workflows/{wid2}/activate", {})
            print(f"Activated sync workflow via /rest (id={wid2})")
        except Exception as e2:
            print(f"Activate failed (run manually in n8n): {e2}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
