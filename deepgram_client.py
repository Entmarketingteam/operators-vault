"""
Transcribe audio via Deepgram with speaker diarization.
Uses DEEPGRAM_API_KEY. punctuate=true, utterances=true for segments.
Supports long-form audio (90+ min) via chunking + stitching with ffmpeg.
"""
from __future__ import annotations

import os
import sys
import subprocess
import tempfile
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


def _get_audio_duration_sec(audio_path: Path) -> float | None:
    """Get audio duration via ffprobe. Returns seconds, or None on error."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1:csv_sep=,", str(audio_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        _log.warning("ffprobe duration check failed: %s", e)
    return None


def _split_audio_chunks(audio_path: Path, chunk_duration_sec: int = 3600) -> list[Path]:
    """
    Split audio into ~chunk_duration_sec chunks via ffmpeg.
    Returns list of temp file paths (caller must clean up).
    Returns [original_path] if split not needed or fails.
    """
    duration = _get_audio_duration_sec(audio_path)
    if not duration or duration < chunk_duration_sec:
        return [audio_path]

    num_chunks = (int(duration) + chunk_duration_sec - 1) // chunk_duration_sec
    _log.info("Splitting %s (%.0f sec) into %d chunks", audio_path.name, duration, num_chunks)

    chunks: list[Path] = []
    try:
        for i in range(num_chunks):
            start_sec = i * chunk_duration_sec
            out_path = Path(tempfile.gettempdir()) / f"chunk_{audio_path.stem}_{i:03d}.m4a"
            cmd = [
                "ffmpeg", "-i", str(audio_path), "-ss", str(start_sec),
                "-t", str(chunk_duration_sec), "-c", "copy", "-y", str(out_path)
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode == 0 and out_path.exists():
                chunks.append(out_path)
                _log.info("  chunk %d/%d: %s", i+1, num_chunks, out_path.name)
            else:
                _log.error("ffmpeg chunk %d failed: %s", i, result.stderr.decode()[:200])
                # Clean up partial chunks on error
                for c in chunks:
                    try: c.unlink()
                    except: pass
                return [audio_path]
    except Exception as e:
        _log.error("Audio chunking failed: %s", e)
        for c in chunks:
            try: c.unlink()
            except: pass
        return [audio_path]

    return chunks if chunks else [audio_path]


def _transcribe_chunk(
    audio_bytes: bytes,
    api_key: str,
    model: str = "nova-2",
    punctuate: bool = True,
    utterances: bool = True,
    diarize: bool = True,
    timeout_sec: int = 1200,
) -> dict[str, Any] | None:
    """Transcribe a single audio chunk via Deepgram SDK with explicit timeout."""
    try:
        client = DeepgramClient(api_key=api_key)
        response = client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model=model,
            smart_format=True,
            punctuate=punctuate,
            utterances=utterances,
            diarize=diarize,
            timeout=timeout_sec,  # 20 min per chunk, prevents unbounded hang
        )
        return response.model_dump()
    except Exception as e:
        if _is_auth_error(e):
            raise
        _log.error("Chunk transcription failed: %s", e)
        return None


def transcribe(
    audio_path: str | Path,
    *,
    api_key: str | None = None,
    punctuate: bool = True,
    utterances: bool = True,
    diarize: bool = True,
    model: str = "nova-2",
    chunk_long_audio: bool = True,
) -> dict[str, Any] | None:
    """
    Transcribe audio file via Deepgram SDK v5, with automatic chunking for 90+ min audio.
    Returns dict with 'results' (and 'results.utterances' when enabled).
    Returns None on non-auth failure or if deepgram-sdk not installed.
    Raises DeepgramAuthError on 401/INVALID_AUTH so callers can abort.

    For audio > ~90 min (chunk_duration_sec=3600): splits into 60-min chunks via ffmpeg,
    transcribes each separately (20-min timeout per chunk), stitches utterances together
    with adjusted timestamps. Temporary chunk files cleaned up automatically.
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

    # Decide: chunk or not
    chunk_paths = [path]
    temp_chunks: list[Path] = []
    if chunk_long_audio:
        chunk_paths = _split_audio_chunks(path, chunk_duration_sec=3600)  # 60-min chunks
        temp_chunks = [p for p in chunk_paths if p != path]  # Mark temps for cleanup

    all_results: list[dict[str, Any]] = []
    time_offset_sec = 0

    for i, chunk_path in enumerate(chunk_paths):
        with open(chunk_path, "rb") as f:
            audio_bytes = f.read()

        _log.info("Transcribing chunk %d/%d: %s (%d bytes, offset %.0f sec)",
                  i+1, len(chunk_paths), chunk_path.name, len(audio_bytes), time_offset_sec)

        result = _transcribe_chunk(
            audio_bytes, api_key, model=model,
            punctuate=punctuate, utterances=utterances, diarize=diarize,
            timeout_sec=1200
        )

        if not result:
            # Clean up temp chunks before returning None
            for tc in temp_chunks:
                try: tc.unlink()
                except: pass
            _log.error("Chunk %d transcription failed, aborting", i+1)
            return None

        # Stitch timestamps: adjust utterance start/end by current offset
        if utterances:
            results_obj = result.get("results") or {}
            utts = results_obj.get("utterances") or []
            for utt in utts:
                if "start" in utt and utt["start"] is not None:
                    utt["start"] = (utt.get("start") or 0) + time_offset_sec
                if "end" in utt and utt["end"] is not None:
                    utt["end"] = (utt.get("end") or 0) + time_offset_sec
            time_offset_sec += 3600  # Assume 60-min chunks; adjust if chunk_duration_sec changes

        all_results.append(result)

    # Clean up temp chunk files
    for tc in temp_chunks:
        try:
            tc.unlink()
            _log.info("Cleaned up temp chunk: %s", tc.name)
        except Exception as e:
            _log.warning("Failed to unlink temp chunk %s: %s", tc, e)

    # Stitch results together
    if len(all_results) == 1:
        _log.info("Transcription complete for %s (single result, no stitching)", path.name)
        return all_results[0]

    # Multiple chunks: merge utterances at top level
    combined_results = all_results[0]
    for subsequent in all_results[1:]:
        results_obj = combined_results.get("results") or {}
        subsequent_obj = subsequent.get("results") or {}

        utts = results_obj.get("utterances") or []
        subsequent_utts = subsequent_obj.get("utterances") or []
        utts.extend(subsequent_utts)

        if "utterances" not in results_obj:
            results_obj["utterances"] = []
        results_obj["utterances"] = utts
        combined_results["results"] = results_obj

    _log.info("Transcription complete for %s (stitched %d chunks)", path.name, len(all_results))
    return combined_results


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
