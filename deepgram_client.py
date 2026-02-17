"""
Transcribe audio via Deepgram with speaker diarization.
Uses DEEPGRAM_API_KEY. punctuate=true, utterances=true for segments.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    from deepgram import Deepgram
except ImportError:
    Deepgram = None  # type: ignore

log = logging.getLogger(__name__)


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
    Transcribe audio file. Returns Deepgram response dict with 'results' and optionally
    'utterances' for segments. Returns None on failure or if deepgram-sdk not installed.
    """
    if Deepgram is None:
        _dlog("[deepgram] transcribe: Deepgram SDK not installed")
        return None
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        _dlog("[deepgram] transcribe: DEEPGRAM_API_KEY not set")
        return None
    path = Path(audio_path)
    if not path.exists():
        _dlog(f"[deepgram] transcribe: file not found {path}")
        return None
    dg = Deepgram(api_key)
    with open(path, "rb") as f:
        payload = f.read()
    options: dict[str, Any] = {
        "punctuate": punctuate,
        "model": model,
        "smart_format": True,
    }
    if utterances:
        options["utterances"] = True
    if diarize:
        options["diarize"] = True
    try:
        res = dg.transcription.sync_prerecorded(payload, options)
        if not res:
            _dlog(f"[deepgram] transcribe: sync_prerecorded returned None/empty for {path}")
        return res
    except Exception as e:
        _dlog(f"[deepgram] transcribe exception for {path}: {type(e).__name__}: {e}")
        log.warning("Deepgram transcribe failed: %s", e, exc_info=True)
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
                _dlog(f"[deepgram] get_raw_text: transcript exists but is empty/whitespace")
    except (IndexError, KeyError, TypeError) as e:
        _dlog(f"[deepgram] get_raw_text parse error: {e!r}, res keys={list(res.keys())[:10] if isinstance(res, dict) else 'not a dict'}")
    # Response present but no transcript (wrong shape, or empty transcript)
    keys = list(res.keys())[:15]
    _dlog(f"[deepgram] get_raw_text: response keys={keys!r}, no transcript extracted. results={res.get('results') is not None if isinstance(res, dict) else 'N/A'}")
    return ""


def get_utterances(res: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Extract utterances (segments with start/end, text, optional speaker).
    Each: { start, end, transcript, speaker? }
    """
    if not res:
        return []
    u = res.get("utterances") or []
    out: list[dict[str, Any]] = []
    for x in u:
        out.append({
            "start": x.get("start"),
            "end": x.get("end"),
            "transcript": (x.get("transcript") or "").strip(),
            "speaker": x.get("speaker"),
        })
    return out
