"""
Local video processor - run this on your machine to process videos.
This bypasses YouTube IP blocking issues on Railway.

Usage:
    python local_process_videos.py

Requirements:
    - DATABASE_URL in .env (pointing to your Supabase database)
    - DEEPGRAM_API_KEY in .env
    - ANTHROPIC_API_KEY in .env
    - yt-dlp installed: pip install yt-dlp
    - ffmpeg installed (for audio extraction)
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load environment
_env = ROOT / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env)
except ImportError:
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip():
                    os.environ.setdefault(k.strip(), v.strip())

if __name__ == "__main__":
    from pipeline import main
    sys.exit(main())
