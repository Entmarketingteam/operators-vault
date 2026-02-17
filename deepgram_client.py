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
    from deepgram import DeepgramClient, PrerecordedOptions
    DEEPGRAM_AVAILABLE = True
except ImportError:
    DeepgramClient = None  # type: ignore
    PrerecordedOptions = None  # type: ignore
    DEEPGRAM_AVAILABLE = False

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
    Uses Deepgram SDK v5 API (DeepgramClient).
    """
    if not DEEPGRAM_AVAILABLE or DeepgramClient is None:
        _dlog("[deepgram] transcribe: Deepgram SDK not installed or unavailable")
        return None
    api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        _dlog("[deepgram] transcribe: DEEPGRAM_API_KEY not set")
        return None
    path = Path(audio_path)
    if not path.exists():
        _dlog(f"[deepgram] transcribe: file not found {path}")
        return None
    
    # Create Deepgram client (v5 API)
    try:
        deepgram = DeepgramClient(api_key)
    except Exception as e:
        _dlog(f"[deepgram] transcribe: failed to create DeepgramClient: {type(e).__name__}: {e}")
        return None
    
    # Read audio file
    with open(path, "rb") as audio_file:
        buffer_data = audio_file.read()
    
    # Build options using PrerecordedOptions (v5 API)
    try:
        options = PrerecordedOptions(
            model=model,
            smart_format=True,
            punctuate=punctuate,
            utterances=utterances,
            diarize=diarize,
        )
    except Exception as e:
        _dlog(f"[deepgram] transcribe: failed to create PrerecordedOptions: {type(e).__name__}: {e}")
        # Fallback to dict if PrerecordedOptions fails
        options = {
            "model": model,
            "smart_format": True,
            "punctuate": punctuate,
            "utterances": utterances,
            "diarize": diarize,
        }
    
    try:
        # Use v5 API: deepgram.listen.rest.v("1").transcribe_file()
        response = deepgram.listen.rest.v("1").transcribe_file(
            {"buffer": buffer_data},
            options
        )
        
        # Deepgram v5 SDK returns a PrerecordedTranscriptionResponse object
        # Convert it to a dict structure compatible with our existing code
        res: dict[str, Any] = {}
        
        # Extract results (contains channels -> alternatives -> transcript)
        if hasattr(response, "results"):
            results = response.results
            # Convert results object to dict if needed
            if hasattr(results, "to_dict"):
                res["results"] = results.to_dict()
            elif hasattr(results, "__dict__"):
                res["results"] = {
                    "channels": getattr(results, "channels", []),
                    "utterances": getattr(results, "utterances", []),
                }
            elif isinstance(results, dict):
                res["results"] = results
            else:
                # Try to access channels directly
                channels = getattr(results, "channels", None)
                if channels:
                    res["results"] = {"channels": channels}
        
        # Extract metadata
        if hasattr(response, "metadata"):
            metadata = response.metadata
            if hasattr(metadata, "to_dict"):
                res["metadata"] = metadata.to_dict()
            elif isinstance(metadata, dict):
                res["metadata"] = metadata
            else:
                res["metadata"] = getattr(metadata, "__dict__", {})
        
        # Extract utterances - in v5, utterances are in results.utterances, not top-level
        # But we also check top-level for compatibility
        utterances = None
        if "results" in res and isinstance(res["results"], dict):
            utterances = res["results"].get("utterances")
        if not utterances and hasattr(response, "utterances"):
            utterances = response.utterances
        if not utterances and hasattr(response, "results") and hasattr(response.results, "utterances"):
            utterances = response.results.utterances
        
        # Normalize utterances to list of dicts
        if utterances:
            if isinstance(utterances, list):
                # Convert utterance objects to dicts if needed
                normalized_utterances = []
                for u in utterances:
                    if isinstance(u, dict):
                        normalized_utterances.append(u)
                    elif hasattr(u, "__dict__"):
                        normalized_utterances.append({
                            "start": getattr(u, "start", None),
                            "end": getattr(u, "end", None),
                            "transcript": getattr(u, "transcript", ""),
                            "speaker": getattr(u, "speaker", None),
                        })
                    elif hasattr(u, "to_dict"):
                        normalized_utterances.append(u.to_dict())
                res["utterances"] = normalized_utterances
            else:
                res["utterances"] = []
        
        # If we still don't have results, try to convert entire response
        if not res or "results" not in res:
            if hasattr(response, "to_dict"):
                res = response.to_dict()
            elif isinstance(response, dict):
                res = response
            else:
                # Last resort: try to serialize response
                _dlog(f"[deepgram] transcribe: could not extract results from response type {type(response)}")
                _dlog(f"[deepgram] transcribe: response attributes: {[a for a in dir(response) if not a.startswith('_')][:20]}")
                return None
        
        if not res:
            _dlog(f"[deepgram] transcribe: transcribe_file returned None/empty for {path}")
            return None
        
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
        # Deepgram v5 structure: res.results.channels[0].alternatives[0].transcript
        results = res.get("results")
        if not results:
            _dlog("[deepgram] get_raw_text: no 'results' key in response")
            return ""
        
        # Handle both dict and object formats
        if isinstance(results, dict):
            channels = results.get("channels", [])
        else:
            # Object format - try to get channels attribute
            channels = getattr(results, "channels", [])
            if not isinstance(channels, list):
                channels = []
        
        if channels and len(channels) > 0:
            ch = channels[0]
            # Handle both dict and object formats for channel
            if isinstance(ch, dict):
                alternatives = ch.get("alternatives", [])
            else:
                alternatives = getattr(ch, "alternatives", [])
                if not isinstance(alternatives, list):
                    alternatives = []
            
            if alternatives and len(alternatives) > 0:
                alt = alternatives[0]
                # Handle both dict and object formats for alternative
                if isinstance(alt, dict):
                    text = (alt.get("transcript") or "").strip()
                else:
                    text = (getattr(alt, "transcript", "") or "").strip()
                
                if text:
                    return text
                else:
                    _dlog(f"[deepgram] get_raw_text: transcript exists but is empty/whitespace")
    except (IndexError, KeyError, TypeError, AttributeError) as e:
        _dlog(f"[deepgram] get_raw_text parse error: {e!r}, res keys={list(res.keys())[:10] if isinstance(res, dict) else 'not a dict'}")
        # Log more details for debugging
        try:
            if isinstance(res, dict):
                _dlog(f"[deepgram] get_raw_text: results type={type(res.get('results'))}, results keys={list(res.get('results', {}).keys())[:10] if isinstance(res.get('results'), dict) else 'not a dict'}")
        except Exception:
            pass
    
    # Response present but no transcript (wrong shape, or empty transcript)
    keys = list(res.keys())[:15] if isinstance(res, dict) else []
    _dlog(f"[deepgram] get_raw_text: response keys={keys!r}, no transcript extracted. results={res.get('results') is not None if isinstance(res, dict) else 'N/A'}")
    return ""


def get_utterances(res: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Extract utterances (segments with start/end, text, optional speaker).
    Each: { start, end, transcript, speaker? }
    Handles both top-level utterances and results.utterances (v5 API).
    """
    if not res:
        return []
    
    # Try top-level utterances first
    u = res.get("utterances")
    
    # If not found, try results.utterances (v5 API structure)
    if not u and isinstance(res.get("results"), dict):
        u = res["results"].get("utterances")
    
    if not u:
        return []
    
    out: list[dict[str, Any]] = []
    for x in u:
        # Handle both dict and object formats
        if isinstance(x, dict):
            out.append({
                "start": x.get("start"),
                "end": x.get("end"),
                "transcript": (x.get("transcript") or "").strip(),
                "speaker": x.get("speaker"),
            })
        else:
            # Handle object format
            out.append({
                "start": getattr(x, "start", None),
                "end": getattr(x, "end", None),
                "transcript": (getattr(x, "transcript", "") or "").strip(),
                "speaker": getattr(x, "speaker", None),
            })
    return out
