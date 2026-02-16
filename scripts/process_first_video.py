"""
Process the first unprocessed video via Railway.
This will fetch a video ID from the database and process it.
"""
from __future__ import annotations

import os
import sys
import time
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


def get_first_unprocessed_video():
    """Get first unprocessed video ID from database via Railway."""
    try:
        import httpx
        
        # We'll need to query the database - let's use a sync endpoint that returns video info
        # Or we can trigger process-new and monitor which video it tries first
        
        # Actually, let's use the /process endpoint with a known video ID
        # First, let's check if we can get video info from a sync
        
        print("Fetching video list...")
        r = httpx.post(f"{RAILWAY_APP_URL}/sync/async", timeout=10.0, verify=False)
        if r.status_code == 202:
            job_id = r.json().get("job_id")
            print(f"Sync job started: {job_id}")
            print("Waiting for sync to complete...")
            
            # Wait for sync to complete
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                r2 = httpx.get(f"{RAILWAY_APP_URL}/jobs/{job_id}", timeout=10.0, verify=False)
                if r2.status_code == 200:
                    data = r2.json()
                    if data.get("status") == "done":
                        result = data.get("result", {})
                        video_ids = result.get("video_ids", [])
                        if video_ids:
                            return video_ids[0]
                        break
                    elif data.get("status") == "error":
                        break
        
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def process_video(video_id: str):
    """Process a single video via Railway."""
    try:
        import httpx
        
        print(f"\nProcessing video: {video_id}")
        print(f"URL: https://www.youtube.com/watch?v={video_id}")
        
        r = httpx.post(
            f"{RAILWAY_APP_URL}/process",
            json={"video_id": video_id},
            timeout=600.0,  # 10 minutes
            verify=False,
        )
        
        if r.status_code == 200:
            result = r.json()
            if result.get("ok"):
                print(f"\n[SUCCESS] Video processed!")
                return True
            else:
                print(f"\n[ERROR] Processing failed: {result}")
                return False
        else:
            print(f"\n[ERROR] HTTP {r.status_code}: {r.text[:500]}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        return False


def main():
    print("="*60)
    print("PROCESSING FIRST VIDEO")
    print("="*60)
    
    # Try to get a video ID
    video_id = get_first_unprocessed_video()
    
    if not video_id:
        # Use a known video ID from the logs we saw earlier
        print("\nUsing a known video ID from recent sync...")
        video_id = "TzyOKA6EhqI"  # From the logs we saw earlier
    
    if video_id:
        success = process_video(video_id)
        return 0 if success else 1
    else:
        print("\n[ERROR] Could not find a video to process")
        print("\nTry manually:")
        print("  python scripts/process_one_video.py [VIDEO_ID]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
