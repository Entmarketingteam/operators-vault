"""
Fetch YouTube video transcripts (auto-generated or manual captions) as a
fallback when yt-dlp audio download is blocked.

Uses the youtube-transcript-api library which accesses YouTube's caption
endpoint directly — this works from datacenter IPs where yt-dlp audio
downloads are blocked by bot detection.

Returns data in the same shape as Deepgram so the pipeline can use it
transparently.
"""
from __future__ import annotations

from structured_logger import get_logger

_log = get_logger("youtube_transcript")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _HAS_LIB = True
except ImportError:
    _HAS_LIB = False


def is_available() -> bool:
    """Return True if youtube-transcript-api is installed."""
    return _HAS_LIB


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en",)) -> dict | None:
    """
    Fetch captions for *video_id* and return a dict that matches the shape
    expected by ``deepgram_client.get_raw_text`` and ``get_utterances``.

    Returns None when captions are unavailable or the library is missing.

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
        ytt_api = YouTubeTranscriptApi()
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
