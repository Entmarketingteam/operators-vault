"""
Import n8n-workflow.json into n8n via the REST API.
Requires N8N_HOST and N8N_API_KEY in .env.

Usage: python scripts/import_n8n_workflow.py
Or: python -m scripts.import_n8n_workflow
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


def main() -> int:
    host = (os.environ.get("N8N_HOST") or "").rstrip("/")
    key = os.environ.get("N8N_API_KEY")
    if not host or not key:
        print("N8N_HOST and N8N_API_KEY must be set in .env.", file=sys.stderr)
        return 1

    path = ROOT / "n8n-workflow.json"
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    # API expects: name, nodes, connections; optional: settings, active, staticData, tags
    payload = {
        "name": data.get("name", "Operators Vault – Process Video"),
        "nodes": data.get("nodes", []),
        "connections": data.get("connections", {}),
        "settings": data.get("settings", {}),
        "active": False,
    }
    if data.get("tags"):
        payload["tags"] = data["tags"]
    if data.get("staticData") is not None:
        payload["staticData"] = data["staticData"]

    url = f"{host}/api/v1/workflows"
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-N8N-API-KEY": key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode())
            wid = out.get("id") or out.get("data", {}).get("id")
            print(f"Workflow imported: {out.get('name', payload['name'])} (id: {wid})")
            return 0
    except Exception as e:
        print(f"Import failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
