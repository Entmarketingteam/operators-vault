"""
Process a single video via Railway API.
Usage: python scripts/process_one_video.py [VIDEO_ID]
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
    video_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not video_id:
        print("Usage: python scripts/process_one_video.py [VIDEO_ID]")
        print("\nTo get a video ID, check your database or use:")
        print("  python scripts/get_unprocessed_videos.py")
        return 1
    
    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1
    
    print(f"Processing video: {video_id}")
    print(f"Using Railway endpoint: {RAILWAY_APP_URL}/process")
    
    try:
        r = httpx.post(
            f"{RAILWAY_APP_URL}/process",
            json={"video_id": video_id},
            timeout=300.0,  # 5 minutes for processing
            verify=False,
        )
        
        if r.status_code == 200:
            result = r.json()
            if result.get("ok"):
                print(f"\n[SUCCESS] Video processed!")
                print(f"  Video ID: {video_id}")
                return 0
            else:
                print(f"\n[ERROR] Processing failed")
                print(f"  Result: {result}")
                return 1
        else:
            print(f"\n[ERROR] HTTP {r.status_code}: {r.text}")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] Exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
