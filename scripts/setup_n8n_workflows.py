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


def _find_workflow(name: str) -> str | None:
    try:
        r = request("GET", "/api/v1/workflows")
        workflows = r.get("data") if isinstance(r.get("data"), list) else (r.get("workflows") or [])
        for w in workflows:
            if isinstance(w, dict) and (w.get("name") or "").strip() == name:
                return str(w.get("id", "")) or None
    except Exception:
        pass
    return None


def _ensure_workflow(filepath: Path, name: str, url: str) -> str:
    data = json.loads(filepath.read_text(encoding="utf-8"))
    for n in data.get("nodes", []):
        if n.get("type") == "n8n-nodes-base.httpRequest" and "parameters" in n:
            n["parameters"]["url"] = url
            break
    payload = {"name": name, "nodes": data["nodes"], "connections": data["connections"], "settings": data.get("settings", {})}
    existing = _find_workflow(name)
    if existing:
        request("PUT", f"/api/v1/workflows/{existing}", payload)
        print(f"Updated: {name} (id={existing})")
        return existing
    out = request("POST", "/api/v1/workflows", payload)
    wid = out.get("id") or (out.get("data") or {}).get("id")
    print(f"Imported: {name} (id={wid})")
    return str(wid)


def main() -> int:
    if not HOST or not KEY:
        print("N8N_HOST and N8N_API_KEY must be set.", file=sys.stderr)
        return 1

    wid1 = _ensure_workflow(ROOT / "n8n-workflow.json", "Operators Vault – Process Video", f"{BASE}/process")
    wid2 = _ensure_workflow(ROOT / "n8n-workflow-fetch-new.json", "Operators Vault – Sync New Episodes", f"{BASE}/sync")

    # Activate sync: try PUT with active, else POST /activate
    for method, path, body in [
        ("PUT", f"/api/v1/workflows/{wid2}", {"active": True}),
        ("POST", f"/api/v1/workflows/{wid2}/activate", None),
    ]:
        try:
            request(method, path, body)
            print(f"Activated sync workflow (id={wid2})")
            break
        except Exception as e:
            if method == "POST":
                print(f"Activate failed (toggle Active in n8n): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
