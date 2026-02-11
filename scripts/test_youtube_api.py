"""
Test YouTube API connection and verify it can fetch videos.
Usage: python scripts/test_youtube_api.py
Requires: YOUTUBE_API_KEY in environment (or .env file)
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
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[ERROR] YOUTUBE_API_KEY not set in environment", file=sys.stderr)
        print("   Set it in .env or export YOUTUBE_API_KEY=...", file=sys.stderr)
        return 1

    print("Testing YouTube API connection...")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")

    # Test 1: Import googleapiclient
    try:
        from googleapiclient.discovery import build
        print("[OK] google-api-python-client imported successfully")
    except ImportError:
        print("[ERROR] google-api-python-client not installed", file=sys.stderr)
        print("   Run: pip install google-api-python-client", file=sys.stderr)
        return 1

    # Test 2: Build YouTube service
    try:
        yt = build("youtube", "v3", developerKey=api_key)
        print("[OK] YouTube API service built successfully")
    except Exception as e:
        print(f"[ERROR] Failed to build YouTube service: {e}", file=sys.stderr)
        return 1

    # Test 3: Resolve a channel handle (9 Operators)
    from youtube_client import resolve_channel_id, get_channel_handle
    print("\nTesting channel resolution...")
    handle = get_channel_handle("9operators")
    print(f"   Channel handle for 9operators: @{handle}")
    
    if not handle:
        print("[WARNING] No channel handle found for 9operators", file=sys.stderr)
        return 1

    try:
        channel_id = resolve_channel_id(handle, api_key=api_key)
        if channel_id:
            print(f"[OK] Resolved @{handle} -> Channel ID: {channel_id}")
        else:
            print(f"[ERROR] Could not resolve @{handle} to channel ID", file=sys.stderr)
            print("   Check if the handle is correct or if API key has proper permissions", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERROR] Error resolving channel: {e}", file=sys.stderr)
        return 1

    # Test 4: Fetch videos from channel
    from youtube_client import fetch_channel_videos
    print("\nTesting video fetch...")
    try:
        videos = fetch_channel_videos(channel_id, podcast="9operators", api_key=api_key, max_results=5)
        if videos:
            print(f"[OK] Successfully fetched {len(videos)} videos")
            print("\n   Sample videos:")
            for i, v in enumerate(videos[:3], 1):
                title = (v.get("title") or "")[:60]
                vid_id = v.get("video_id", "")
                views = v.get("view_count", 0)
                print(f"   {i}. {title} (ID: {vid_id}, Views: {views:,})")
        else:
            print("[WARNING] No videos returned (channel may be empty or API quota exceeded)", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERROR] Error fetching videos: {e}", file=sys.stderr)
        print("   This could indicate:", file=sys.stderr)
        print("   - Invalid API key", file=sys.stderr)
        print("   - API quota exceeded", file=sys.stderr)
        print("   - Network connectivity issue", file=sys.stderr)
        return 1

    # Test 5: Test playlist fetch (if TITANS playlist is set)
    playlist_id = os.environ.get("YOUTUBE_PLAYLIST_TITANS")
    if playlist_id:
        from youtube_client import fetch_playlist_videos
        print(f"\nTesting playlist fetch (TITANS: {playlist_id})...")
        try:
            playlist_videos = fetch_playlist_videos(playlist_id, podcast="titans", api_key=api_key, max_results=3)
            if playlist_videos:
                print(f"[OK] Successfully fetched {len(playlist_videos)} videos from playlist")
            else:
                print("[WARNING] No videos returned from playlist", file=sys.stderr)
        except Exception as e:
            print(f"[WARNING] Error fetching playlist: {e}", file=sys.stderr)
    else:
        print("\n[INFO] YOUTUBE_PLAYLIST_TITANS not set, skipping playlist test")

    print("\n[SUCCESS] All YouTube API tests passed!")
    print("\nNext steps:")
    print("   - Run: python pipeline.py --fetch-new")
    print("   - Or call: POST /fetch-new on your Railway API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
