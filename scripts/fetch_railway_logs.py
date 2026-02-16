"""
Fetch recent Railway logs to diagnose video processing issues.
Requires: RAILWAY_API_TOKEN in .env
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

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
MAIN_SERVICE_ID = "64aa9bda-8cc2-4a79-acf0-4fd10cca1301"  # From previous logs


def _load_railway_ids() -> tuple[str, str] | None:
    """Returns (project_id, environment_id)."""
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


def fetch_logs_via_api(service_id: str, limit: int = 100):
    """Fetch logs using Railway GraphQL API."""
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        print("RAILWAY_API_TOKEN required", file=sys.stderr)
        return None
    
    ids = _load_railway_ids()
    if not ids:
        print("Run 'railway link' or set RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID", file=sys.stderr)
        return None
    
    project_id, environment_id = ids
    
    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return None
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Try to fetch logs via GraphQL
    # Note: Railway's log API might be different - this is an attempt
    query = """
    query deploymentLogs($serviceId: String!, $limit: Int!) {
      deploymentLogs(serviceId: $serviceId, limit: $limit) {
        message
        timestamp
        level
      }
    }
    """
    
    try:
        r = httpx.post(
            RAILWAY_GRAPHQL,
            json={
                "query": query,
                "variables": {
                    "serviceId": service_id,
                    "limit": limit,
                }
            },
            headers=headers,
            timeout=30.0,
            verify=False,
        )
        
        if r.status_code == 200:
            out = r.json()
            if not out.get("errors"):
                return out.get("data", {}).get("deploymentLogs", [])
            else:
                print(f"GraphQL errors: {out['errors']}", file=sys.stderr)
        else:
            print(f"HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
    except Exception as e:
        print(f"Error fetching logs: {e}", file=sys.stderr)
    
    return None


def main():
    print("="*60)
    print("FETCHING RAILWAY LOGS")
    print("="*60)
    
    print(f"\nService ID: {MAIN_SERVICE_ID}")
    print("Fetching recent logs...\n")
    
    logs = fetch_logs_via_api(MAIN_SERVICE_ID, limit=200)
    
    if logs:
        print(f"Found {len(logs)} log entries\n")
        
        # Filter for audio/processing related logs
        audio_logs = []
        error_logs = []
        processing_logs = []
        
        for log in logs:
            msg = log.get("message", "").lower()
            if "[audio]" in msg or "audio" in msg or "yt-dlp" in msg:
                audio_logs.append(log)
            if "error" in msg or "failed" in msg:
                error_logs.append(log)
            if "process" in msg or "transcribe" in msg or "insight" in msg:
                processing_logs.append(log)
        
        if audio_logs:
            print("="*60)
            print("AUDIO DOWNLOAD LOGS")
            print("="*60)
            for log in audio_logs[-20:]:  # Last 20 audio logs
                ts = log.get("timestamp", "")
                msg = log.get("message", "")
                print(f"{ts} | {msg}")
        
        if error_logs:
            print("\n" + "="*60)
            print("ERROR LOGS")
            print("="*60)
            for log in error_logs[-20:]:  # Last 20 errors
                ts = log.get("timestamp", "")
                msg = log.get("message", "")
                print(f"{ts} | {msg}")
        
        if processing_logs:
            print("\n" + "="*60)
            print("PROCESSING LOGS")
            print("="*60)
            for log in processing_logs[-20:]:  # Last 20 processing logs
                ts = log.get("timestamp", "")
                msg = log.get("message", "")
                print(f"{ts} | {msg}")
    else:
        print("\n[INFO] Could not fetch logs via API")
        print("\nTo check logs manually:")
        print("1. Go to Railway Dashboard: https://railway.app")
        print("2. Navigate to your project -> superb-smile service")
        print("3. Click on 'Logs' tab")
        print("4. Look for lines containing:")
        print("   - [audio] ERROR:")
        print("   - [audio] download failed")
        print("   - yt-dlp output:")
        print("\nOr use Railway CLI:")
        print("  railway logs --service superb-smile")
    
    print("\n" + "="*60)
    print("LOG FETCH COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
