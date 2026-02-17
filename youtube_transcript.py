"""
Fetch YouTube video transcripts (auto-generated or manual captions) as a
fallback when yt-dlp audio download is blocked.

Uses the youtube-transcript-api library which accesses YouTube's caption
endpoint directly — this works from datacenter IPs where yt-dlp audio
downloads are blocked by bot detection.

When YouTube also blocks caption requests (common for cloud-provider IPs),
set the ``YT_DLP_PROXY`` environment variable to a residential/rotating
proxy URL.  The same variable is shared with yt-dlp so a single config
covers both audio downloads and caption fetches.

Returns data in the same shape as Deepgram so the pipeline can use it
transparently.
"""
from __future__ import annotations

import os

from structured_logger import get_logger

_log = get_logger("youtube_transcript")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _HAS_LIB = True
except ImportError:
    _HAS_LIB = False

try:
    from youtube_transcript_api.proxies import GenericProxyConfig
    _HAS_PROXY = True
except ImportError:
    _HAS_PROXY = False


_PROXY_PLACEHOLDER_HOSTS = ("example.com", "example.org", "example.net")


def _build_proxy_config():
    """Build a proxy config from ``YT_DLP_PROXY`` env var, if set.

    Skips placeholder URLs (containing ``example.com`` etc.) so that
    leftover ``.env.example`` values don't break caption fetching.
    """
    proxy_url = os.environ.get("YT_DLP_PROXY", "").strip()
    if not proxy_url:
        return None
    # Skip placeholder URLs left over from .env.example
    lower = proxy_url.lower()
    for host in _PROXY_PLACEHOLDER_HOSTS:
        if host in lower:
            _log.warning(
                "Ignoring YT_DLP_PROXY for captions: looks like a placeholder (%s)",
                proxy_url[:60],
            )
            return None
    if not _HAS_PROXY:
        _log.warning(
            "YT_DLP_PROXY is set but youtube-transcript-api proxy support "
            "is unavailable (upgrade to >= 1.0.0)"
        )
        return None
    _log.info("Using proxy for YouTube captions", extra={"proxy": proxy_url[:30] + "..."})
    return GenericProxyConfig(https_url=proxy_url, http_url=proxy_url)


def is_available() -> bool:
    """Return True if youtube-transcript-api is installed."""
    return _HAS_LIB


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en",)) -> dict | None:
    """
    Fetch captions for *video_id* and return a dict that matches the shape
    expected by ``deepgram_client.get_raw_text`` and ``get_utterances``.

    Returns None when captions are unavailable or the library is missing.

    Reads the ``YT_DLP_PROXY`` environment variable and, when set, routes
    caption requests through the proxy to avoid IP blocks.

    The returned dict has the same structure as a Deepgram response::

        {
            "results": {
                "channels": [{"alternatives": [{"transcript": "full text ..."}]}],
                "utterances": [
                    {"start": 0.0, "end": 3.5, "transcript": "segment", "speaker": 0},
                    ...
                ],
            },
            "metadata": {"source": "youtube_captions"},
        }
    """
    if not _HAS_LIB:
        _log.warning("youtube-transcript-api not installed, cannot fetch captions")
        return None

    try:
        proxy_config = _build_proxy_config()
        kwargs = {}
        if proxy_config is not None:
            kwargs["proxy_config"] = proxy_config
        ytt_api = YouTubeTranscriptApi(**kwargs)
        transcript = ytt_api.fetch(video_id, languages=list(languages))
        snippets = transcript.snippets
    except Exception as e:
        _log.warning(
            "Could not fetch YouTube captions for %s: %s: %s",
            video_id, type(e).__name__, e,
        )
        return None

    if not snippets:
        _log.info("No caption snippets returned for %s", video_id)
        return None

    # Build full text
    full_text = " ".join(s.text.replace("\n", " ").strip() for s in snippets if s.text.strip())

    if not full_text.strip():
        _log.info("YouTube captions were empty for %s", video_id)
        return None

    # Build utterance-like segments (speaker is always 0 since captions don't
    # carry speaker info)
    utterances = []
    for s in snippets:
        text = s.text.replace("\n", " ").strip()
        if not text:
            continue
        utterances.append({
            "start": s.start,
            "end": s.start + s.duration,
            "transcript": text,
            "speaker": 0,
        })

    _log.info(
        "Fetched YouTube captions for %s: %d chars, %d segments",
        video_id, len(full_text), len(utterances),
    )

    return {
        "results": {
            "channels": [{"alternatives": [{"transcript": full_text}]}],
            "utterances": utterances,
        },
        "metadata": {"source": "youtube_captions"},
    }
