"""
Fetch episodes from 9 Operators, Marketing Operator, Finance Operator, and TITANS.
Supports: (1) CSV seed lists, (2) YouTube Data API by channel, (3) playlist for TITANS.
Tag each video with podcast: 9operators | marketing_operator | finance_operators | titans.
"""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

# YouTube @handles for fetch-new (override via YOUTUBE_CHANNEL_<PODCAST> env)
DEFAULT_CHANNEL_HANDLES = {
    "9operators": "Operators9",
    "marketing_operator": "MarketingOperators",
    "finance_operators": "FinanceOperatorsFOPS",
    "titans": "Operators9",  # same channel; or use YOUTUBE_PLAYLIST_TITANS for playlist
}

# TITANS: set YOUTUBE_PLAYLIST_TITANS to a playlist ID to fetch by playlist instead of channel
# (e.g. Operators Titans playlist on YouTube)

# CSV seed paths (Windows); override via env or pass to functions
# TITANS CSV: titles often start with "Operators Titans" (e.g. "Operators Titans E005: Peak 21 (with president Roman Khan)"); stored as-is; UI strips prefix when showing TITANS.
# operators_and_titans: single scraped CSV (e.g. Chrome extension) with both shows; podcast inferred per row from title.
DEFAULT_CSV_PATHS = {
    "9operators": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Operators Podcast Video Youtube Links.csv"),
    "marketing_operator": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Marketing Operators Podcast Video Youtube Links.csv"),
    "finance_operators": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Finance Operators Podcast Video Youtube Links.csv"),
    "titans": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "TITANS Podcast Video Youtube Links.csv"),
    "operators_and_titans": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Operators and Titans Podcast Historically until February 10 2026.csv"),
}


def _parse_duration(dur: str) -> int | None:
    """Parse '1:27:30' or '45:00' to seconds. Returns None if unparseable."""
    if not dur or not isinstance(dur, str):
        return None
    dur = str(dur).strip()
    parts = [int(x) for x in re.findall(r"\d+", dur)]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    # h:m:s
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def _infer_podcast_from_filename(path: str) -> str:
    p = (path or "").lower()
    if "titans" in p:
        return "titans"
    if "marketing" in p and "operators" in p:
        return "marketing_operator"
    if "finance" in p and "operators" in p:
        return "finance_operators"
    return "9operators"


def _infer_podcast_from_title(title: str) -> str:
    """Infer 9operators vs titans from title. Use for combined Operators + TITANS channel CSV."""
    t = (title or "").strip()
    if t.startswith("Operators Titans ") or t.startswith("Operator Titans "):
        return "titans"
    return "9operators"


def load_from_csv(
    csv_path: str,
    *,
    podcast: str | None = None,
    min_duration_sec: int = 300,
    infer_podcast_from_title: bool = False,
) -> list[dict[str, Any]]:
    """
    Load video list from a CSV.

    Chrome-extension / scraped format (header row is skipped automatically if it has no video ID):
      col 0 = URL, col 1 = thumbnail URL, col 2 = duration (e.g. 1:27:30), col 3 = title,
      col 4 = views text, col 5 = relative date.
    We use col 0 (URL), col 2 (duration), col 3 (title). Dedupes by video_id.
    Set infer_podcast_from_title=True for a combined Operators + TITANS CSV: titles starting
    with "Operators Titans" / "Operator Titans" -> titans, else 9operators.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    path = Path(csv_path)
    if not path.exists():
        return out
    default_podcast = podcast if podcast is not None else _infer_podcast_from_filename(csv_path)
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 1:
                continue
            url = (row[0] or "").strip()
            vid = _extract_video_id(url)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            duration_str = (row[2] if len(row) > 2 else "") or ""
            duration_sec = _parse_duration(duration_str)
            if duration_sec is not None and duration_sec < min_duration_sec:
                continue
            title = (row[3] if len(row) > 3 else "") or ""
            row_podcast = _infer_podcast_from_title(title) if infer_podcast_from_title else default_podcast
            out.append({
                "video_id": vid,
                "title": title,
                "duration_seconds": duration_sec,
                "podcast": row_podcast,
                "url": url or "",
            })
    return out


def load_all_seed_csvs(
    paths: dict[str, str] | None = None,
    *,
    min_duration_sec: int = 300,
) -> list[dict[str, Any]]:
    """
    Load from all default (or given) CSV paths. Key by podcast; value = path.
    Use key "operators_and_titans" for a single CSV that contains both 9 Operators and TITANS
    (podcast inferred per row from title). Merges and dedupes by video_id (first occurrence wins).
    """
    paths = paths or DEFAULT_CSV_PATHS
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pod, p in paths.items():
        if not p or not Path(p).exists():
            continue
        if pod == "operators_and_titans":
            for v in load_from_csv(p, min_duration_sec=min_duration_sec, infer_podcast_from_title=True):
                if v["video_id"] not in seen:
                    seen.add(v["video_id"])
                    merged.append(v)
        else:
            for v in load_from_csv(p, podcast=pod, min_duration_sec=min_duration_sec):
                if v["video_id"] not in seen:
                    seen.add(v["video_id"])
                    merged.append(v)
    return merged


def get_channel_handle(podcast: str) -> str | None:
    """Resolve podcast to @handle. Env override: YOUTUBE_CHANNEL_FINANCE_OPERATORS etc."""
    key = (podcast or "").upper().replace("-", "_")
    env_var = f"YOUTUBE_CHANNEL_{key}"
    v = os.environ.get(env_var, "").strip()
    if v:
        return v.lstrip("@")
    return (DEFAULT_CHANNEL_HANDLES or {}).get(podcast or "")


def resolve_channel_id(for_handle: str, api_key: str | None = None) -> str | None:
    """
    Resolve a YouTube @handle (e.g. 'Operators9', 'MarketingOperators') to channel ID.
    Use fetch_channel_videos(channel_id, podcast=...) after this.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return None
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return None
    handle = (for_handle or "").strip().lstrip("@")
    if not handle:
        return None
    yt = build("youtube", "v3", developerKey=api_key)
    req = yt.channels().list(part="id", forHandle=handle)
    res = req.execute()
    items = res.get("items") or []
    return items[0]["id"] if items else None


def _video_item_to_record(
    it: dict,
    *,
    podcast: str,
    channel_id: str | None = None,
) -> dict[str, Any]:
    """Build one video record from videos.list item (snippet + contentDetails + statistics)."""
    vid = it.get("id")
    sn = it.get("snippet") or {}
    cd = it.get("contentDetails") or {}
    stats = it.get("statistics") or {}
    ch_id = channel_id or sn.get("channelId") or ""
    dur_iso = cd.get("duration") or ""
    sec = _parse_iso8601_duration(dur_iso)
    published_at = sn.get("publishedAt")
    # Thumbnail: prefer medium, else high
    thumb = (sn.get("thumbnails") or {}).get("medium") or (sn.get("thumbnails") or {}).get("high") or {}
    thumbnail_url = thumb.get("url") if isinstance(thumb, dict) else None
    tags_list = sn.get("tags")
    if isinstance(tags_list, list):
        tags_str = ",".join(str(t) for t in tags_list[:50])  # cap for DB
    else:
        tags_str = None
    view_count = stats.get("viewCount")
    if view_count is not None:
        try:
            view_count = int(view_count)
        except (TypeError, ValueError):
            view_count = None
    like_count = stats.get("likeCount")
    if like_count is not None:
        try:
            like_count = int(like_count)
        except (TypeError, ValueError):
            like_count = None
    comment_count = stats.get("commentCount")
    if comment_count is not None:
        try:
            comment_count = int(comment_count)
        except (TypeError, ValueError):
            comment_count = None
    return {
        "video_id": vid,
        "title": sn.get("title") or "",
        "duration_seconds": sec,
        "channel_id": ch_id,
        "channel_title": sn.get("channelTitle") or "",
        "podcast": podcast,
        "published_at": published_at,
        "view_count": view_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "thumbnail_url": thumbnail_url,
        "description": (sn.get("description") or "")[:10000] if sn.get("description") else None,
        "tags": tags_str,
    }


def fetch_channel_videos(
    channel_id: str,
    *,
    podcast: str,
    api_key: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Fetch recent videos from a YouTube channel via Data API v3.
    Includes statistics (view_count, like_count, comment_count), thumbnail, description, channel_title.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return []
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return []
    yt = build("youtube", "v3", developerKey=api_key)
    req = yt.search().list(
        part="id,snippet",
        channelId=channel_id,
        type="video",
        order="date",
        maxResults=max_results,
    )
    res = req.execute()
    vid_ids = [e["id"]["videoId"] for e in (res.get("items") or []) if "videoId" in e.get("id", {})]
    if not vid_ids:
        return []
    vreq = yt.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(vid_ids),
    )
    vres = vreq.execute()
    out: list[dict[str, Any]] = []
    for it in (vres.get("items") or []):
        out.append(_video_item_to_record(it, podcast=podcast, channel_id=channel_id))
    return out


def get_playlist_id(podcast: str) -> str | None:
    """Return playlist ID for podcast if set (e.g. YOUTUBE_PLAYLIST_TITANS)."""
    key = (podcast or "").upper().replace("-", "_")
    env_var = f"YOUTUBE_PLAYLIST_{key}"
    return os.environ.get(env_var, "").strip() or None


def fetch_playlist_videos(
    playlist_id: str,
    *,
    podcast: str,
    api_key: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Fetch videos from a YouTube playlist. Same record shape as fetch_channel_videos.
    Use for TITANS when YOUTUBE_PLAYLIST_TITANS is set.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return []
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return []
    yt = build("youtube", "v3", developerKey=api_key)
    vid_ids: list[str] = []
    next_page_token = None
    while len(vid_ids) < max_results:
        preq = yt.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=min(50, max_results - len(vid_ids)),
            pageToken=next_page_token or "",
        )
        pres = preq.execute()
        for item in (pres.get("items") or []):
            vid = (item.get("snippet") or {}).get("resourceId", {}).get("videoId")
            if vid:
                vid_ids.append(vid)
        next_page_token = pres.get("nextPageToken")
        if not next_page_token:
            break
    if not vid_ids:
        return []
    vreq = yt.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(vid_ids[:50]),
    )
    vres = vreq.execute()
    out: list[dict[str, Any]] = []
    for it in (vres.get("items") or []):
        out.append(_video_item_to_record(it, podcast=podcast))
    return out


def _parse_iso8601_duration(s: str) -> int | None:
    """PT1H27M30S -> 5250."""
    if not s or not s.startswith("PT"):
        return None
    s = s[2:].upper()
    h = m = sec = 0
    for mo in re.finditer(r"(\d+)([HMS])", s):
        v, u = int(mo.group(1)), mo.group(2)
        if u == "H":
            h = v
        elif u == "M":
            m = v
        elif u == "S":
            sec = v
    return h * 3600 + m * 60 + sec
