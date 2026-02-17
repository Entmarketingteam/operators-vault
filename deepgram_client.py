"""
Transcribe audio via Deepgram with speaker diarization.
Uses DEEPGRAM_API_KEY. punctuate=true, utterances=true for segments.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    from deepgram import DeepgramClient
except ImportError:
    DeepgramClient = None  # type: ignore

from structured_logger import get_logger

_log = get_logger("deepgram_client")


def _dlog(msg: str) -> None:
    """Log to stderr so it appears in Railway / job capture."""
    print(msg, file=sys.stderr, flush=True)


def transcribe(
    audio_path: str | Path,
    *,
    api_key: str | None = None,
    punctuate: bool = True,
    utterances: bool = True,
    diarize: bool = True,
    model: str = "nova-2",
) -> dict[str, Any] | None:
    """
    Transcribe audio file via Deepgram SDK v5.
    Returns dict with 'results' (and 'results.utterances' when enabled).
    Returns None on failure or if deepgram-sdk not installed.
    """
    if DeepgramClient is None:
        _dlog("[deepgram] transcribe: DeepgramClient not available (SDK not installed)")
        _log.warning("DeepgramClient not available (SDK not installed)")
        return None
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        _dlog("[deepgram] transcribe: DEEPGRAM_API_KEY not set")
        _log.warning("DEEPGRAM_API_KEY not set")
        return None
    path = Path(audio_path)
    if not path.exists():
        _dlog(f"[deepgram] transcribe: file not found {path}")
        _log.warning("Audio file not found: %s", path)
        return None

    with open(path, "rb") as f:
        audio_bytes = f.read()

    _log.info("Transcribing %s (%d bytes)", path.name, len(audio_bytes))

    try:
        client = DeepgramClient(api_key=api_key)
        response = client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model=model,
            smart_format=True,
            punctuate=punctuate,
            utterances=utterances,
            diarize=diarize,
        )
        # Convert Pydantic model -> dict so get_raw_text/get_utterances work unchanged
        result = response.model_dump()
        _log.info("Transcription complete for %s", path.name)
        return result
    except Exception as e:
        _dlog(f"[deepgram] transcribe exception for {path}: {type(e).__name__}: {e}")
        _log.error("Transcription failed for %s: %s: %s", path.name, type(e).__name__, e)
        return None


def get_raw_text(res: dict[str, Any] | None) -> str:
    """Extract full transcript text from Deepgram response."""
    if not res:
        _dlog("[deepgram] get_raw_text: res is None/empty")
        return ""
    try:
        ch = (res.get("results") or {}).get("channels") or []
        if ch and (ch[0].get("alternatives")):
            text = (ch[0]["alternatives"][0].get("transcript") or "").strip()
            if text:
                return text
            else:
                _dlog("[deepgram] get_raw_text: transcript exists but is empty/whitespace")
    except (IndexError, KeyError, TypeError) as e:
        _dlog(f"[deepgram] get_raw_text parse error: {e!r}, res keys={list(res.keys())[:10] if isinstance(res, dict) else 'not a dict'}")
    # Response present but no transcript (wrong shape, or empty transcript)
    keys = list(res.keys())[:15] if isinstance(res, dict) else []
    _dlog(f"[deepgram] get_raw_text: response keys={keys!r}, no transcript extracted.")
    return ""


def get_utterances(res: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Extract utterances (segments with start/end, text, optional speaker).
    Each: { start, end, transcript, speaker? }
    """
    if not res:
        return []
    # v5 SDK: utterances under results.utterances
    # v2 SDK: utterances at top level (fallback)
    results = res.get("results") or {}
    u = results.get("utterances") or res.get("utterances") or []
    out: list[dict[str, Any]] = []
    for x in u:
        out.append({
            "start": x.get("start"),
            "end": x.get("end"),
            "transcript": (x.get("transcript") or "").strip(),
            "speaker": x.get("speaker"),
        })
    return out
