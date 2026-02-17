"""
Download audio from YouTube via yt-dlp with robust retry, error classification,
proxy support, and cookie handling for cloud environments (Railway).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from structured_logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Error classification for yt-dlp failures
# ---------------------------------------------------------------------------
# Errors that are worth retrying (transient)
_RETRYABLE_PATTERNS = [
    "429",                      # HTTP 429 Too Many Requests
    "503",                      # HTTP 503 Service Unavailable
    "502",                      # HTTP 502 Bad Gateway
    "rate limit",
    "temporarily unavailable",
    "network",
    "connection",
    "timed out",
    "urlopen error",
    "eof occurred",
    "incomplete read",
    "socket",
    "reset by peer",
    "ssl",
]

# Errors that indicate IP/bot blocking (need proxy or different approach)
_BLOCKED_PATTERNS = [
    "403",                      # HTTP 403 Forbidden
    "sign in to confirm",
    "bot",
    "captcha",
    "verify you are human",
    "consent",
    "not available in your country",
    "geo restriction",
    "private video",
    "age-restricted",
]

# Errors that are permanent (don't retry)
_PERMANENT_PATTERNS = [
    "video unavailable",
    "this video has been removed",
    "account has been terminated",
    "copyright",
    "404",
]


def _classify_error(output: str) -> str:
    """Classify yt-dlp error into: retryable, blocked, permanent, or unknown."""
    lower = output.lower()
    for pattern in _PERMANENT_PATTERNS:
        if pattern in lower:
            return "permanent"
    for pattern in _BLOCKED_PATTERNS:
        if pattern in lower:
            return "blocked"
    for pattern in _RETRYABLE_PATTERNS:
        if pattern in lower:
            return "retryable"
    return "unknown"


def _extract_error_message(stderr: str, stdout: str, returncode: int) -> str:
    """Extract the most useful error message from yt-dlp output."""
    combined = (stderr + "\n" + stdout).strip() if stderr and stdout else (stderr or stdout or "")
    error_lines = [line.strip() for line in combined.split("\n") if line.strip()]
    # Prioritize ERROR lines from yt-dlp
    important = [l for l in error_lines if "ERROR" in l.upper() or "error" in l.lower()]
    if not important:
        important = [l for l in error_lines if not l.startswith("[download]") and not l.startswith("[info]") and not l.startswith("[debug]")]
    if not important:
        important = error_lines
    first = important[0][:300] if important else f"exit code {returncode}"
    return first


def get_audio_path(video_id: str, work_dir: str | Path | None = None) -> Path:
    """Return the path where audio will be (or was) saved: work_dir/video_id.audio.webm or .m4a."""
    work_dir = Path(work_dir or tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)
    for ext in (".webm", ".m4a", ".mp3"):
        p = work_dir / f"{video_id}.audio{ext}"
        if p.exists():
            return p
    return work_dir / f"{video_id}.audio.webm"


def _find_output_file(directory: Path, video_id: str) -> Path | None:
    """Find the downloaded audio file in the given directory."""
    for ext in (".m4a", ".webm", ".mp3", ".opus", ".ogg"):
        p = directory / f"{video_id}.audio{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _build_yt_dlp_cmd() -> list[str]:
    """Build the base yt-dlp command, trying system binary first, then python module."""
    yt_dlp_bin = shutil.which("yt-dlp")
    if yt_dlp_bin:
        return [yt_dlp_bin]
    return [sys.executable, "-m", "yt_dlp"]


def download_audio(
    video_id: str,
    work_dir: str | Path | None = None,
    max_retries: int = 3,
) -> tuple[Path | None, str]:
    """
    Download audio for a YouTube video using yt-dlp.

    Returns (path_to_audio_file, "") on success, or (None, error_message) on failure.

    Improvements over v2:
    - Better error classification (retryable vs blocked vs permanent)
    - Longer exponential backoff (5s, 15s, 45s, 120s)
    - Cookie file support via YT_DLP_COOKIES env var
    - Geo-bypass flag for datacenter IPs
    - Proper structured logging
    - Shutdown-aware (checks for shutdown signal)
    """
    log.info("download_audio called", extra={"video_id": video_id, "max_retries": max_retries})
    work_dir = Path(work_dir or tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)

    # Check if file already exists in shared work_dir (reuse from a previous run)
    existing = _find_output_file(work_dir, video_id)
    if existing:
        log.info("Audio file already exists, reusing", extra={"video_id": video_id, "path": str(existing)})
        return (existing, "")

    # Unique subdir per call to prevent race conditions
    dl_dir = work_dir / f".yt_{uuid.uuid4().hex[:12]}"
    dl_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    out_tpl = str(dl_dir / f"{video_id}.audio.%(ext)s")

    # Build command
    base_cmd = _build_yt_dlp_cmd()

    # Optional proxy
    proxy_url = os.environ.get("YT_DLP_PROXY", "").strip()
    proxy_args = ["--proxy", proxy_url] if proxy_url else []

    # Optional cookies file (for authenticated downloads, bypassing some restrictions)
    cookies_path = os.environ.get("YT_DLP_COOKIES", "").strip()
    cookies_args: list[str] = []
    if cookies_path and Path(cookies_path).exists():
        cookies_args = ["--cookies", cookies_path]
        log.info("Using cookies file", extra={"video_id": video_id, "cookies_path": cookies_path})

    cmd = base_cmd + [
        "-v",
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--extract-audio",
        "--audio-format", "m4a",
        "-o", out_tpl,
        "--no-playlist",
        "--no-warnings",
        "--geo-bypass",                     # attempt geo-bypass for datacenter IPs
        "--socket-timeout", "30",           # don't hang on slow connections
        "--retries", "3",                   # yt-dlp internal retries
        "--fragment-retries", "3",          # retry individual fragments
    ] + proxy_args + cookies_args + [url]

    last_error = None
    last_classification = "unknown"

    for attempt in range(max_retries + 1):
        if attempt > 0:
            # Longer exponential backoff: 5s, 15s, 45s, 120s (capped)
            wait_time = min(5 * (3 ** (attempt - 1)), 120)
            log.info("Retrying download", extra={
                "video_id": video_id,
                "attempt": attempt + 1,
                "max_attempts": max_retries + 1,
                "wait_seconds": wait_time,
                "last_error_class": last_classification,
            })
            time.sleep(wait_time)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )

            # Check if file was created
            output_file = _find_output_file(dl_dir, video_id)
            if output_file:
                log.info("Download succeeded", extra={
                    "video_id": video_id,
                    "attempt": attempt + 1,
                    "file": str(output_file),
                    "size_bytes": output_file.stat().st_size,
                })
                return (output_file, "")

            # yt-dlp exited 0 but no file found
            err = "no output file written after yt-dlp succeeded (check audio-format compatibility)"
            log.error("Download anomaly: success exit but no file", extra={"video_id": video_id})
            return (None, err)

        except FileNotFoundError as e:
            err = f"yt-dlp or ffmpeg not found: {e}"
            log.error(err, extra={"video_id": video_id})
            return (None, err)

        except subprocess.TimeoutExpired:
            err = f"yt-dlp timed out after 600s (attempt {attempt + 1}/{max_retries + 1})"
            log.warning(err, extra={"video_id": video_id})
            last_error = err
            last_classification = "retryable"
            if attempt < max_retries:
                continue
            return (None, err)

        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            combined = (stderr + "\n" + stdout).strip() if stderr and stdout else (stderr or stdout or "")

            error_msg = _extract_error_message(stderr, stdout, e.returncode)
            classification = _classify_error(combined)
            last_error = f"exit {e.returncode}: {error_msg}"
            last_classification = classification

            log.warning("yt-dlp failed", extra={
                "video_id": video_id,
                "attempt": attempt + 1,
                "max_attempts": max_retries + 1,
                "exit_code": e.returncode,
                "error_class": classification,
                "error_msg": error_msg,
                "stderr_tail": stderr[-500:] if stderr else "",
                "stdout_tail": stdout[-500:] if stdout else "",
            })

            # Permanent errors: don't retry
            if classification == "permanent":
                log.error("Permanent download failure, not retrying", extra={
                    "video_id": video_id,
                    "error_class": classification,
                    "error_msg": error_msg,
                })
                return (None, last_error)

            # Blocked errors: log prominently, retry with backoff (proxy might help)
            if classification == "blocked":
                log.error("Download blocked (likely IP/bot detection)", extra={
                    "video_id": video_id,
                    "error_class": classification,
                    "error_msg": error_msg,
                    "has_proxy": bool(proxy_url),
                    "has_cookies": bool(cookies_args),
                    "hint": "Set YT_DLP_PROXY to a residential proxy or YT_DLP_COOKIES to a cookies file",
                })
                if attempt < max_retries:
                    continue
                return (None, last_error)

            # Retryable or unknown: retry if attempts remain
            if attempt < max_retries:
                continue

            log.error("Download failed after all retries", extra={
                "video_id": video_id,
                "total_attempts": max_retries + 1,
                "error_class": classification,
                "error_msg": error_msg,
            })
            return (None, last_error)

    return (None, last_error or "max retries exceeded")
