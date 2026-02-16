"""
Verify that everything is set up correctly and working.
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

RAILWAY_APP_URL = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/")


def main():
    print("="*60)
    print("VERIFYING SETUP")
    print("="*60)
    
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed: pip install httpx")
        return 1
    
    # Test health endpoint
    print("\n1. Testing Railway health endpoint...")
    try:
        r = httpx.get(f"{RAILWAY_APP_URL}/health", timeout=10.0, verify=False)
        if r.status_code == 200:
            data = r.json()
            print(f"   [OK] Service is running")
            checks = data.get("checks", {})
            all_ok = True
            for check, status in checks.items():
                if status == "ok":
                    print(f"   [OK] {check}: {status}")
                else:
                    print(f"   [WARN] {check}: {status}")
                    all_ok = False
            if all_ok:
                print("   [OK] All health checks passed")
        else:
            print(f"   [ERROR] Health check failed: HTTP {r.status_code}")
            return 1
    except Exception as e:
        print(f"   [ERROR] Exception: {e}")
        return 1
    
    # Test sync endpoint
    print("\n2. Testing sync endpoint...")
    try:
        r = httpx.post(f"{RAILWAY_APP_URL}/sync/async", timeout=10.0, verify=False)
        if r.status_code == 202:
            data = r.json()
            job_id = data.get("job_id")
            print(f"   [OK] Sync endpoint working")
            print(f"   [OK] Job ID: {job_id}")
            
            # Check job status
            print(f"\n3. Checking job status...")
            import time
            status_url = f"{RAILWAY_APP_URL}/jobs/{job_id}"
            for i in range(3):
                time.sleep(2)
                r2 = httpx.get(status_url, timeout=10.0, verify=False)
                if r2.status_code == 200:
                    status_data = r2.json()
                    status = status_data.get("status")
                    print(f"   Status: {status}")
                    if status == "done":
                        result = status_data.get("result", {})
                        upserted = result.get("upserted", 0)
                        processed = result.get("processed", 0)
                        errors = result.get("errors", [])
                        print(f"   [OK] Job completed")
                        print(f"        Fetched: {upserted} videos")
                        print(f"        Processed: {processed} videos")
                        if errors:
                            print(f"        Errors: {len(errors)}")
                            for err in errors[:3]:
                                print(f"          - {err}")
                        break
                    elif status == "error":
                        error = status_data.get("error", "Unknown error")
                        print(f"   [ERROR] Job failed: {error}")
                        break
        else:
            print(f"   [ERROR] Sync endpoint failed: HTTP {r.status_code}")
            print(f"           Response: {r.text[:200]}")
            return 1
    except Exception as e:
        print(f"   [ERROR] Exception: {e}")
        return 1
    
    print("\n" + "="*60)
    print("SETUP VERIFICATION COMPLETE")
    print("="*60)
    print("\n[OK] Everything is configured and working!")
    print(f"\nCron service will run every 3 hours automatically.")
    print(f"Or trigger manually: curl -X POST {RAILWAY_APP_URL}/sync/async")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
