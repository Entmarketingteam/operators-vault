"""
Download audio from YouTube via yt-dlp. Reusable as-is for Operators Vault.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


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


def download_audio(video_id: str, work_dir: str | Path | None = None) -> Path | None:
    """
    Download audio for a YouTube video. Uses yt-dlp.
    Returns path to the audio file, or None on failure.
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
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    # find the file (ext can vary)
    for ext in (".webm", ".m4a", ".mp3"):
        p = work_dir / f"{video_id}.audio{ext}"
        if p.exists():
            return p
    return None
