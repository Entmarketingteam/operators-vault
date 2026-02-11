"""
Trigger sync on Railway: fetch new videos and process all unprocessed videos.
Usage: python scripts/trigger_sync.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    import httpx
except ImportError:
    print("httpx not installed. pip install httpx", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    api_url = "https://superb-smile-production.up.railway.app"
    
    print("Triggering sync (fetch-new + process-all)...")
    print(f"API: {api_url}")
    
    # Prefer GET /trigger-sync (returns 202 quickly; avoids Railway 502)
    try:
        with httpx.Client(timeout=30.0, verify=False) as client:
            # Prefer GET trigger (Railway-friendly)
            r = client.get(f"{api_url}/trigger-sync", timeout=15.0)
            if r.status_code == 401:
                print("[ERROR] Set SYNC_TRIGGER_KEY in Railway and pass ?key=... or leave unset to allow no key.")
                return 1
            if r.status_code == 202:
                job_data = r.json()
                job_id = job_data.get("job_id")
                print(f"\n[OK] Sync started! Job ID: {job_id}")
                print(f"Status: {job_data.get('status')}")
                print(f"\nMonitor: GET {api_url}/jobs/{job_id}")
                print(f"Stats:   GET {api_url}/stats")
                for _ in range(5):
                    time.sleep(5)
                    try:
                        status_r = client.get(f"{api_url}/jobs/{job_id}", timeout=10.0)
                        if status_r.status_code == 200:
                            d = status_r.json()
                            print(f"  Status: {d.get('status')}")
                            if d.get("status") == "done":
                                res = d.get("result", {})
                                print(f"\n[SUCCESS] Upserted: {res.get('upserted', 0)}, Processed: {res.get('processed', 0)}")
                                return 0
                            if d.get("status") == "error":
                                print(f"\n[ERROR] {d.get('error')}")
                                return 1
                    except Exception as e:
                        print(f"  Poll error: {e}")
                return 0
            # Fallback: POST /sync/async
            try:
                r = client.post(f"{api_url}/sync/async", timeout=15.0)
            except Exception:
                r = None
            
            if r and r.status_code == 202:
                job_data = r.json()
                job_id = job_data.get("job_id")
                print(f"\n[OK] Sync started! Job ID: {job_id}")
                print(f"Status: {job_data.get('status')}")
                print(f"\nMonitor progress:")
                print(f"  GET {api_url}/jobs/{job_id}")
                print(f"\nOr check stats:")
                print(f"  GET {api_url}/stats")
                
                # Poll for status a few times
                print("\nPolling job status (will check a few times)...")
                for i in range(5):
                    time.sleep(5)
                    try:
                        status_r = client.get(f"{api_url}/jobs/{job_id}", timeout=10.0)
                        if status_r.status_code == 200:
                            status_data = status_r.json()
                            status = status_data.get("status")
                            print(f"  [{i+1}/5] Status: {status}")
                            
                            if status == "done":
                                result = status_data.get("result", {})
                                print(f"\n[SUCCESS] Sync completed!")
                                print(f"  Videos fetched: {result.get('upserted', 0)}")
                                print(f"  Videos processed: {result.get('processed', 0)}")
                                print(f"  Video IDs: {result.get('video_ids', [])[:5]}...")
                                return 0
                            elif status == "error":
                                error = status_data.get("error", "Unknown error")
                                print(f"\n[ERROR] Sync failed: {error}")
                                return 1
                    except Exception as e:
                        print(f"  [{i+1}/5] Error checking status: {e}")
                
                print("\n[INFO] Job still running. Check status manually:")
                print(f"  GET {api_url}/jobs/{job_id}")
                return 0
            else:
                # Fall back to separate calls
                print("\n[INFO] Async sync unavailable, trying separate endpoints...")
                
                # Fetch new
                print("\n[1/2] Fetching new videos...")
                try:
                    fetch_r = client.post(f"{api_url}/fetch-new", timeout=60.0)
                    if fetch_r.status_code == 200:
                        fetch_data = fetch_r.json()
                        upserted = fetch_data.get("upserted", 0)
                        print(f"[OK] Fetched {upserted} new videos")
                    else:
                        print(f"[WARNING] Fetch-new returned {fetch_r.status_code}: {fetch_r.text}")
                except Exception as e:
                    print(f"[WARNING] Fetch-new failed: {e}")
                
                # Process new (async)
                print("\n[2/2] Starting processing (async)...")
                try:
                    process_r = client.post(f"{api_url}/process-new/async", timeout=10.0)
                    if process_r.status_code == 202:
                        job_data = process_r.json()
                        job_id = job_data.get("job_id")
                        print(f"[OK] Processing started! Job ID: {job_id}")
                        print(f"\nMonitor progress:")
                        print(f"  GET {api_url}/jobs/{job_id}")
                        print(f"\nOr check stats:")
                        print(f"  GET {api_url}/stats")
                        return 0
                    else:
                        print(f"[ERROR] Process-new/async returned {process_r.status_code}: {process_r.text}")
                        return 1
                except Exception as e:
                    print(f"[ERROR] Failed to start processing: {e}")
                    return 1
    except Exception as e:
        print(f"[ERROR] Failed to trigger sync: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
