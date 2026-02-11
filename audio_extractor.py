"""
Download audio from YouTube via yt-dlp. Reusable as-is for Operators Vault.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
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


def download_audio(video_id: str, work_dir: str | Path | None = None) -> tuple[Path | None, str]:
    """
    Download audio for a YouTube video. Uses yt-dlp.
    Returns (path_to_audio_file, "") on success, or (None, error_message) on failure.
    error_message is a short one-line hint for logs (e.g. yt-dlp stderr).
    """
    work_dir = Path(work_dir or tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_tpl = str(work_dir / f"{video_id}.audio.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--extract-audio",
        "--audio-format", "webm",  # Deepgram likes webm; fallback handled by -f
        "-o", out_tpl,
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        url,
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError as e:
        err = f"yt-dlp or ffmpeg not found: {e}"
        log.warning("%s", err)
        return (None, err)
    except subprocess.TimeoutExpired:
        err = "yt-dlp timed out"
        log.warning("%s for %s", err, video_id)
        return (None, err)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip() if e.stderr else ""
        stdout = (e.stdout or "").strip() if e.stdout else ""
        first_line = (stderr or stdout or str(e)).split("\n")[0].strip()[:200]
        err = f"exit {e.returncode}: {first_line}"
        log.warning("yt-dlp failed for %s: %s", video_id, err)
        return (None, err)
    # Find the file (ext can vary)
    for ext in (".webm", ".m4a", ".mp3"):
        p = work_dir / f"{video_id}.audio{ext}"
        if p.exists():
            return (p, "")
    return (None, "no output file written after yt-dlp")
