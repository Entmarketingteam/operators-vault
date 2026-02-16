"""
Download audio from YouTube via yt-dlp. Reusable as-is for Operators Vault.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)


def get_audio_path(video_id: str, work_dir: str | Path | None = None) -> Path:
    """Return the path where audio will be (or was) saved: work_dir/video_id.audio.webm or .m4a."""
    work_dir = Path(work_dir or tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)
    # yt-dlp often uses .webm or .m4a; we'll check both
    for ext in (".webm", ".m4a", ".mp3"):
        p = work_dir / f"{video_id}.audio{ext}"
        if p.exists():
            return p
    return work_dir / f"{video_id}.audio.webm"


def download_audio(video_id: str, work_dir: str | Path | None = None, max_retries: int = 2) -> tuple[Path | None, str]:
    """
    Download audio for a YouTube video. Uses yt-dlp.
    Returns (path_to_audio_file, "") on success, or (None, error_message) on failure.
    error_message is a short one-line hint for logs (e.g. yt-dlp stderr).
    
    Args:
        video_id: YouTube video ID
        work_dir: Directory to save audio file
        max_retries: Number of retry attempts for transient failures (default: 2)
    """
    work_dir = Path(work_dir or tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_tpl = str(work_dir / f"{video_id}.audio.%(ext)s")
    
    # Check if file already exists
    for ext in (".webm", ".m4a", ".mp3"):
        p = work_dir / f"{video_id}.audio{ext}"
        if p.exists():
            log.debug("Audio file already exists for %s: %s", video_id, p)
            return (p, "")
    
    # Try yt-dlp command first, fallback to python -m yt_dlp
    import shutil
    yt_dlp_cmd = shutil.which("yt-dlp")
    if not yt_dlp_cmd:
        # Fallback to python module
        yt_dlp_cmd = [sys.executable, "-m", "yt_dlp"]
    else:
        yt_dlp_cmd = [yt_dlp_cmd]
    
    cmd = yt_dlp_cmd + [
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--extract-audio",
        "--audio-format", "m4a",  # Use m4a (supported by yt-dlp); Deepgram accepts m4a
        "-o", out_tpl,
        "--no-playlist",
        "--no-warnings",
        # TEST BRANCH: iOS client + mobile UA to try bypassing YouTube blocks (zero cost)
        "--extractor-args", "youtube:player_client=ios,web",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        url,
    ]
    # Optional proxy fallback if set (e.g. residential); insert before url
    proxy_url = os.environ.get("YT_DLP_PROXY")
    if proxy_url:
        cmd.insert(-1, proxy_url)
        cmd.insert(-1, "--proxy")

    last_error = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait_time = min(2 ** attempt, 10)  # Exponential backoff: 2s, 4s, max 10s
            print(f"  [audio] Retry {attempt}/{max_retries} after {wait_time}s...", flush=True)
            time.sleep(wait_time)
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            # Log success for debugging
            if result.stdout:
                log.debug("yt-dlp stdout for %s: %s", video_id, result.stdout[:200])
            
            # Check if file was created
            for ext in (".webm", ".m4a", ".mp3"):
                p = work_dir / f"{video_id}.audio{ext}"
                if p.exists():
                    return (p, "")
            
            # If we get here, yt-dlp succeeded but no file was created
            err = "no output file written after yt-dlp succeeded"
            last_error = err
            print(f"  [audio] ERROR: {err}", flush=True)
            # Don't retry if yt-dlp succeeded but no file - this is likely a configuration issue
            return (None, err)
            
        except FileNotFoundError as e:
            err = f"yt-dlp or ffmpeg not found: {e}"
            log.warning("%s", err)
            print(f"  [audio] ERROR: {err}", flush=True)
            return (None, err)  # Don't retry - this is a system configuration issue
            
        except subprocess.TimeoutExpired:
            err = f"yt-dlp timed out after 600s (attempt {attempt + 1}/{max_retries + 1})"
            log.warning("%s for %s", err, video_id)
            last_error = err
            if attempt < max_retries:
                continue  # Retry timeout errors
            print(f"  [audio] ERROR: {err}", flush=True)
            return (None, err)
            
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip() if e.stderr else ""
            stdout = (e.stdout or "").strip() if e.stdout else ""
            # Combine both outputs for better error visibility
            combined = (stderr + "\n" + stdout).strip() if stderr and stdout else (stderr or stdout or "")
            # Always print raw output for Railway logs (yt-dlp errors often start with [youtube], [download])
            print(f"  [audio] FULL STDERR: {stderr[:1000]}", file=sys.stderr, flush=True)
            print(f"  [audio] FULL STDOUT: {stdout[:1000]}", file=sys.stderr, flush=True)
            # Extract meaningful error lines — do NOT filter out [ lines (yt-dlp uses [youtube] ERROR: ...)
            error_lines = [line.strip() for line in combined.split("\n") if line.strip()]
            important_lines = [l for l in error_lines if "ERROR" in l.upper() or "error" in l.lower()]
            if not important_lines:
                important_lines = [l for l in error_lines if not l.startswith("[download]") and not l.startswith("[info]")]
            if not important_lines:
                important_lines = error_lines
            first_error = important_lines[0][:300] if important_lines else f"exit code {e.returncode}"
            err = f"exit {e.returncode}: {first_error}"
            last_error = err
            
            # Check if error is retryable (HTTP 429, 503, network errors)
            retryable = False
            if combined:
                combined_lower = combined.lower()
                retryable = any(x in combined_lower for x in ["429", "503", "rate limit", "temporarily unavailable", "network", "connection"])
            
            if retryable and attempt < max_retries:
                log.warning("yt-dlp failed (retryable) for %s: %s", video_id, err)
                continue  # Retry retryable errors
            
            # Non-retryable error or max retries reached
            log.warning("yt-dlp failed for %s: %s", video_id, err)
            print(f"  [audio] ERROR: {err}", flush=True)
            if combined:
                print(f"  [audio] yt-dlp output: {combined[:500]}", flush=True)
            return (None, err)
    
    # Should not reach here, but handle it
    return (None, last_error or "max retries exceeded")
