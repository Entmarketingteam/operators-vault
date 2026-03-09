"""
Full YouTube channel backfill via uploads playlist pagination.
Fetches ALL videos from each channel, filters to full episodes (>= 20 min),
upserts to Supabase videos table, then triggers Railway process-new.

Usage:
  python3 scripts/backfill_youtube_full.py
  python3 scripts/backfill_youtube_full.py --dry-run     # counts only
  python3 scripts/backfill_youtube_full.py --podcast 9operators
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import psycopg2
import warnings
warnings.filterwarnings("ignore")
from googleapiclient.discovery import build

RAILWAY_URL = "https://superb-smile-production.up.railway.app"
MIN_DURATION_SEC = 20 * 60  # 20 minutes — full episodes only

CHANNELS = {
    "9operators": {
        "handle": "Operators9",
        "channel_id": "UCuGneytUApsb7SEynqoZ0ug",
        "uploads_playlist": "UUuGneytUApsb7SEynqoZ0ug",
    },
    "marketing_operator": {
        "handle": "MarketingOperators",
        "channel_id": "UCLCl2hY_E08Q9q2X1p6ouMA",
        "uploads_playlist": "UULCl2hY_E08Q9q2X1p6ouMA",
    },
    "finance_operators": {
        "handle": "FinanceOperatorsFOPS",
        "channel_id": "UChL5rAxddwU_EnbhZofhDjw",
        "uploads_playlist": "UUhL5rAxddwU_EnbhZofhDjw",
    },
}


def parse_iso8601_duration(s: str) -> int:
    import re
    if not s or not s.startswith("PT"):
        return 0
    h = m = sec = 0
    for mo in re.finditer(r"(\d+)([HMS])", s[2:].upper()):
        v, u = int(mo.group(1)), mo.group(2)
        if u == "H": h = v
        elif u == "M": m = v
        elif u == "S": sec = v
    return h * 3600 + m * 60 + sec


def fetch_all_video_ids(yt, playlist_id: str) -> list[str]:
    """Page through all items in a playlist and return video IDs."""
    ids = []
    next_page = None
    page = 0
    while True:
        kwargs = dict(part="snippet", playlistId=playlist_id, maxResults=50)
        if next_page:
            kwargs["pageToken"] = next_page
        res = yt.playlistItems().list(**kwargs).execute()
        for item in res.get("items", []):
            vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                ids.append(vid)
        next_page = res.get("nextPageToken")
        page += 1
        if page % 10 == 0:
            print(f"    ... fetched {len(ids)} IDs so far")
        if not next_page:
            break
    return ids


def fetch_video_details(yt, video_ids: list[str], podcast: str, channel_id: str) -> list[dict]:
    """Batch fetch video details in chunks of 50."""
    records = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        res = yt.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(chunk),
        ).execute()
        for it in res.get("items", []):
            sn = it.get("snippet", {})
            cd = it.get("contentDetails", {})
            stats = it.get("statistics", {})
            dur = parse_iso8601_duration(cd.get("duration", ""))
            if dur < MIN_DURATION_SEC:
                continue  # skip shorts/clips
            thumb = (sn.get("thumbnails") or {})
            thumb_url = (thumb.get("medium") or thumb.get("high") or {}).get("url")
            records.append({
                "video_id": it["id"],
                "title": sn.get("title", ""),
                "podcast": podcast,
                "duration_seconds": dur,
                "channel_id": channel_id,
                "channel_title": sn.get("channelTitle", ""),
                "published_at": sn.get("publishedAt"),
                "thumbnail_url": thumb_url,
                "view_count": int(stats["viewCount"]) if stats.get("viewCount") else None,
                "like_count": int(stats["likeCount"]) if stats.get("likeCount") else None,
                "description": (sn.get("description") or "")[:5000],
            })
    return records


def get_existing_video_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT video_id FROM videos")
        return {r[0] for r in cur.fetchall()}


def upsert_videos(conn, records: list[dict]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for r in records:
            cur.execute("""
                INSERT INTO videos (video_id, podcast, title, duration_seconds, channel_id, channel_title, published_at, thumbnail_url, like_count, description)
                VALUES (%(video_id)s, %(podcast)s, %(title)s, %(duration_seconds)s, %(channel_id)s, %(channel_title)s, %(published_at)s, %(thumbnail_url)s, %(like_count)s, %(description)s)
                ON CONFLICT (video_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    thumbnail_url = COALESCE(EXCLUDED.thumbnail_url, videos.thumbnail_url),
                    like_count = COALESCE(EXCLUDED.like_count, videos.like_count),
                    description = COALESCE(EXCLUDED.description, videos.description),
                    channel_title = COALESCE(EXCLUDED.channel_title, videos.channel_title)
            """, r)
            inserted += cur.rowcount
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--podcast", help="Only run this podcast")
    parser.add_argument("--trigger-process", action="store_true", default=True,
                        help="Call Railway /process-new/async after upsert (default: true)")
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY not set"); sys.exit(1)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set"); sys.exit(1)

    yt = build("youtube", "v3", developerKey=api_key)

    targets = {k: v for k, v in CHANNELS.items() if not args.podcast or k == args.podcast}
    if not targets:
        print(f"No match for --podcast {args.podcast}"); sys.exit(1)

    conn = psycopg2.connect(db_url, sslmode="require")
    existing = get_existing_video_ids(conn)
    print(f"Existing videos in DB: {len(existing)}")

    total_new = 0
    for podcast, cfg in targets.items():
        print(f"\n[{podcast}] Fetching all video IDs from uploads playlist...")
        all_ids = fetch_all_video_ids(yt, cfg["uploads_playlist"])
        print(f"[{podcast}] Total on channel: {len(all_ids)}")

        new_ids = [i for i in all_ids if i not in existing]
        print(f"[{podcast}] New (not in DB): {len(new_ids)}")

        if args.dry_run or not new_ids:
            continue

        print(f"[{podcast}] Fetching details for {len(new_ids)} videos (filtering <20min)...")
        records = fetch_video_details(yt, new_ids, podcast, cfg["channel_id"])
        print(f"[{podcast}] Full episodes (>=20min): {len(records)}")

        n = upsert_videos(conn, records)
        print(f"[{podcast}] Upserted: {n}")
        total_new += len(records)

    conn.close()

    if args.dry_run:
        print("\nDry run complete. No data written.")
        return

    print(f"\nTotal new episodes upserted: {total_new}")

    if total_new > 0 and args.trigger_process:
        import requests
        print("\nTriggering Railway /process-new/async...")
        try:
            r = requests.post(f"{RAILWAY_URL}/process-new/async", timeout=30)
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  WARNING: trigger failed: {e}")
            print(f"  Run manually: curl -X POST {RAILWAY_URL}/process-new/async")


if __name__ == "__main__":
    main()
