"""
Run sync locally: fetch new videos and process all unprocessed videos.
Uses DATABASE_URL and YOUTUBE_API_KEY from environment (.env or Doppler).
Usage: python scripts/run_sync_local.py
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


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Add it to .env or use Doppler.", file=sys.stderr)
        return 1
    
    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    if not youtube_key:
        print("[WARNING] YOUTUBE_API_KEY not set. Fetch-new will be skipped.", file=sys.stderr)
    
    print("Starting sync: fetch-new + process-all...")
    print(f"Database: {db_url[:30]}...")
    if youtube_key:
        print(f"YouTube API: {youtube_key[:10]}...")
    
    # Import pipeline functions
    sys.path.insert(0, str(ROOT))
    from pipeline import _fetch_new, _get_unprocessed, _process_one
    
    import psycopg2
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    try:
        # Step 1: Fetch new videos
        if youtube_key:
            print("\n[1/2] Fetching new videos from YouTube...")
            try:
                upserted = _fetch_new(cur, max_per_channel=50, min_duration_sec=300)
                conn.commit()
                print(f"[OK] Fetched {upserted} new videos")
            except Exception as e:
                print(f"[ERROR] Failed to fetch videos: {e}", file=sys.stderr)
                conn.rollback()
        else:
            print("\n[1/2] Skipping fetch-new (no YOUTUBE_API_KEY)")
            upserted = 0
        
        # Step 2: Process all unprocessed videos
        print("\n[2/2] Processing all unprocessed videos...")
        rows = _get_unprocessed(cur)
        total = len(rows)
        print(f"Found {total} unprocessed videos")
        
        if total == 0:
            print("[INFO] No videos to process!")
            return 0
        
        processed = []
        failed = []
        
        for i, (video_id, podcast) in enumerate(rows, 1):
            print(f"\n[{i}/{total}] Processing {video_id} ({podcast})...")
            try:
                ok = _process_one(video_id, podcast)
                if ok:
                    processed.append(video_id)
                    print(f"  [OK] Processed successfully")
                else:
                    failed.append(video_id)
                    print(f"  [FAILED] Processing failed")
            except Exception as e:
                failed.append(video_id)
                print(f"  [ERROR] {e}", file=sys.stderr)
        
        print(f"\n[SUMMARY]")
        print(f"  Videos fetched: {upserted}")
        print(f"  Videos processed: {len(processed)}/{total}")
        print(f"  Videos failed: {len(failed)}")
        
        if failed:
            print(f"\nFailed video IDs: {failed[:10]}...")
        
        return 0 if len(failed) == 0 else 1
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
