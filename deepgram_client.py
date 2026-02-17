"""
Transcribe audio via Deepgram with speaker diarization.
Uses DEEPGRAM_API_KEY. punctuate=true, utterances=true for segments.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx

try:
    from deepgram import DeepgramClient
except ImportError:
    DeepgramClient = None  # type: ignore

from structured_logger import get_logger

_log = get_logger("deepgram_client")


class DeepgramAuthError(Exception):
    """Raised when Deepgram returns 401 / INVALID_AUTH. Callers should abort the batch."""
    pass


def _dlog(msg: str) -> None:
    """Log to stderr so it appears in Railway / job capture."""
    print(msg, file=sys.stderr, flush=True)


def _is_auth_error(exc: Exception) -> bool:
    """Detect 401 / INVALID_AUTH from Deepgram SDK exceptions."""
    exc_str = str(exc)
    if "401" in exc_str or "INVALID_AUTH" in exc_str or "Invalid credentials" in exc_str:
        return True
    # Check for status_code attribute (Deepgram SDK ApiError)
    if hasattr(exc, "status_code") and getattr(exc, "status_code", None) == 401:
        return True
    return False


def check_api_key(api_key: str | None = None) -> bool:
    """
    Validate the Deepgram API key via GET /v1/projects.
    Returns True if valid. Raises DeepgramAuthError if invalid.
    """
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise DeepgramAuthError("DEEPGRAM_API_KEY not set")
    try:
        resp = httpx.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        if resp.status_code == 401:
            _log.error("Deepgram API key invalid (401 from /v1/projects)")
            raise DeepgramAuthError(
                f"Deepgram API key is invalid (HTTP 401). "
                f"Check DEEPGRAM_API_KEY env var. Response: {resp.text[:200]}"
            )
        if resp.status_code == 200:
            _log.info("Deepgram API key validated successfully")
            return True
        _log.warning("Deepgram key check returned HTTP %d: %s", resp.status_code, resp.text[:200])
        return True  # Non-401 errors (e.g. 403 scope) mean the key itself is valid
    except DeepgramAuthError:
        raise
    except Exception as e:
        _log.warning("Deepgram key check failed (network?): %s", e)
        return True  # Network errors shouldn't block sync; the real transcribe call will fail


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
    Returns None on non-auth failure or if deepgram-sdk not installed.
    Raises DeepgramAuthError on 401/INVALID_AUTH so callers can abort.
    """
    if DeepgramClient is None:
        _dlog("[deepgram] transcribe: DeepgramClient not available (SDK not installed)")
        _log.warning("DeepgramClient not available (SDK not installed)")
        return None
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        _dlog("[deepgram] transcribe: DEEPGRAM_API_KEY not set")
        _log.warning("DEEPGRAM_API_KEY not set")
        raise DeepgramAuthError("DEEPGRAM_API_KEY not set")
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
        if _is_auth_error(e):
            raise DeepgramAuthError(
                f"Deepgram API key is invalid (401 Unauthorized). "
                f"Update DEEPGRAM_API_KEY env var. Original: {type(e).__name__}: {e}"
            ) from e
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
