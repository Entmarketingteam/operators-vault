"""
Set up Railway Cron Job to automatically sync when new videos are posted.
Requires: RAILWAY_API_TOKEN, RAILWAY_PROJECT_ID (or run 'railway link' first).
Usage: python scripts/setup_railway_cron.py
"""
from __future__ import annotations

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


def _load_railway_ids() -> tuple[str, str, str] | None:
    """Load Railway project/environment/service IDs from env or .railway/config.json."""
    p = os.environ.get("RAILWAY_PROJECT_ID")
    e = os.environ.get("RAILWAY_ENVIRONMENT_ID")
    s = os.environ.get("RAILWAY_SERVICE_ID")
    if p and e:
        return (p, e, s or "")
    cfg = Path.home() / ".railway" / "config.json"
    if cfg.exists():
        import json
        data = json.loads(cfg.read_text())
        proj = data.get("project")
        env = data.get("environment")
        svc = data.get("service")
        if proj and env:
            return (proj, env, svc or "")
    return None


def main() -> int:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN required. Get from Railway → Account → Tokens", file=sys.stderr)
        return 1

    ids = _load_railway_ids()
    if not ids:
        print("Run 'railway link' or set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID", file=sys.stderr)
        return 1

    project_id, env_id, service_id = ids
    api_url = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/")
    sync_key = os.environ.get("SYNC_TRIGGER_KEY", "").strip()
    
    # Build trigger URL
    trigger_url = f"{api_url}/trigger-sync"
    if sync_key:
        trigger_url += f"?key={sync_key}"

    print("Setting up Railway Cron Job for automatic sync...")
    print(f"Project: {project_id}")
    print(f"Environment: {env_id}")
    print(f"Trigger URL: {trigger_url}")
    print("\n[INFO] Railway Cron Jobs must be set up via Railway Dashboard:")
    print("  1. Go to Railway → Your Project → New → Cron Job")
    print("  2. Set schedule: '0 */3 * * *' (every 3 hours) or '0 * * * *' (every hour)")
    print(f"  3. Set command: curl -X GET '{trigger_url}'")
    print("  4. Or use Railway's HTTP Cron template and set URL to:", trigger_url)
    print("\nAlternatively, use n8n workflow (already configured):")
    print("  python scripts/setup_n8n_workflows.py")
    print("  Then activate 'Operators Vault – Sync New Episodes' in n8n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
