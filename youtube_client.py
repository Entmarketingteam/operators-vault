"""
Fetch episodes from 9 Operators, Marketing Operator, and Finance Operator.
Supports: (1) CSV seed lists, (2) YouTube Data API by channel.
Tag each video with podcast: 9operators | marketing_operator | finance_operators.
"""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

# CSV seed paths (Windows); override via env or pass to functions
DEFAULT_CSV_PATHS = {
    "9operators": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Operators Podcast Video Youtube Links.csv"),
    "marketing_operator": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Marketing Operators Podcast Video Youtube Links.csv"),
    "finance_operators": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Finance Operators Podcast Video Youtube Links.csv"),
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
    if "marketing" in p and "operators" in p:
        return "marketing_operator"
    if "finance" in p and "operators" in p:
        return "finance_operators"
    return "9operators"


def load_from_csv(
    csv_path: str,
    *,
    podcast: str | None = None,
    min_duration_sec: int = 300,
) -> list[dict[str, Any]]:
    """
    Load video list from a CSV. Format: col 1 = URL, col 3 = duration (e.g. 1:27:30), col 4 = title.
    Dedupes by video_id. Optionally skips duration under min_duration_sec.
    """
    if podcast is None:
        podcast = _infer_podcast_from_filename(csv_path)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    path = Path(csv_path)
    if not path.exists():
        return out
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
            out.append({
                "video_id": vid,
                "title": title,
                "duration_seconds": duration_sec,
                "podcast": podcast,
            })
    return out


def load_all_seed_csvs(
    paths: dict[str, str] | None = None,
    *,
    min_duration_sec: int = 300,
) -> list[dict[str, Any]]:
    """
    Load from all default (or given) CSV paths. Key by podcast; value = path.
    Merges and dedupes by video_id across CSVs (first occurrence wins).
    """
    paths = paths or DEFAULT_CSV_PATHS
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pod, p in paths.items():
        for v in load_from_csv(p, podcast=pod, min_duration_sec=min_duration_sec):
            if v["video_id"] not in seen:
                seen.add(v["video_id"])
                merged.append(v)
    return merged


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


def fetch_channel_videos(
    channel_id: str,
    *,
    podcast: str,
    api_key: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Fetch recent videos from a YouTube channel via Data API v3.
    api_key from YOUTUBE_API_KEY env if not passed.
    For 9 Operators use channel from resolve_channel_id('Operators9');
    Marketing Operator: resolve_channel_id('MarketingOperators').
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
    out: list[dict[str, Any]] = []
    vid_ids = [e["id"]["videoId"] for e in (res.get("items") or []) if "videoId" in e.get("id", {})]
    if not vid_ids:
        return out
    # get duration from videos.list
    vreq = yt.videos().list(part="snippet,contentDetails", id=",".join(vid_ids))
    vres = vreq.execute()
    for it in (vres.get("items") or []):
        vid = it.get("id")
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        dur_iso = cd.get("duration") or ""
        # PT1H27M30S -> seconds
        sec = _parse_iso8601_duration(dur_iso)
        out.append({
            "video_id": vid,
            "title": sn.get("title") or "",
            "duration_seconds": sec,
            "channel_id": channel_id,
            "podcast": podcast,
        })
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
