"""
Transcribe audio via Deepgram with speaker diarization.
Uses DEEPGRAM_API_KEY. punctuate=true, utterances=true for segments.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from deepgram import Deepgram
except ImportError:
    Deepgram = None  # type: ignore


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
        return None
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        return None
    path = Path(audio_path)
    if not path.exists():
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
        return res
    except Exception:
        return None


def get_raw_text(res: dict[str, Any] | None) -> str:
    """Extract full transcript text from Deepgram response."""
    if not res:
        return ""
    try:
        ch = (res.get("results") or {}).get("channels") or []
        if ch and (ch[0].get("alternatives")):
            return (ch[0]["alternatives"][0].get("transcript") or "").strip()
    except (IndexError, KeyError, TypeError):
        pass
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
