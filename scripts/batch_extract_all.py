#!/usr/bin/env python3
"""
Batch extract insights for all episodes with 0 insights.
Runs sequentially to avoid agent server rate limiting.

Usage:
  python batch_extract_all.py              # Process all 0-insight episodes
  python batch_extract_all.py --start 10   # Skip first 10 (resume)
  python batch_extract_all.py --limit 20   # Process at most 20 episodes
"""
import os
import sys
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "extract_episode_insights.py"
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"batch_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_zero_insight_episodes() -> list[tuple[str, str, str, int]]:
    """Returns list of (video_id, title, podcast, seg_count) ordered by seg_count desc."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.video_id, v.title, v.podcast, COUNT(DISTINCT s.id) as seg_count
                FROM videos v
                LEFT JOIN transcriptions t ON t.video_id = v.video_id
                LEFT JOIN segments s ON s.transcription_id = t.id
                LEFT JOIN insights i ON i.video_id = v.video_id
                GROUP BY v.video_id, v.title, v.podcast
                HAVING COUNT(DISTINCT i.id) = 0 AND COUNT(DISTINCT s.id) > 0
                ORDER BY seg_count DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="Skip first N episodes")
    parser.add_argument("--limit", type=int, default=None, help="Max episodes to process")
    args = parser.parse_args()

    log(f"Batch extraction starting — log: {LOG_FILE}")
    log("Querying 0-insight episodes from DB...")

    episodes = get_zero_insight_episodes()
    total_available = len(episodes)

    episodes = episodes[args.start:]
    if args.limit:
        episodes = episodes[:args.limit]

    log(f"Total available: {total_available} | Starting at: {args.start} | Processing: {len(episodes)}")
    log("")

    success = 0
    failed = 0
    total_stored = 0

    for i, (video_id, title, podcast, seg_count) in enumerate(episodes):
        global_idx = i + args.start + 1
        progress = f"[{global_idx}/{total_available}]"

        log(f"{progress} {video_id} | {podcast} | segs:{seg_count} | {title[:55]}")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), video_id],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )

        output = result.stdout + result.stderr
        # Extract stored count from output
        stored = 0
        for line in output.splitlines():
            if "Stored:" in line and "insights" in line:
                try:
                    stored = int(line.split("Stored:")[1].split("new")[0].strip())
                except Exception:
                    pass
            if line.strip():
                log(f"  {line.rstrip()}")

        if result.returncode == 0:
            success += 1
            total_stored += stored
            log(f"  => OK: {stored} insights stored")
        else:
            failed += 1
            log(f"  => FAILED (exit {result.returncode})")

        # Small delay to avoid rate limiting
        time.sleep(3)

    log("")
    log(f"{'='*60}")
    log(f"Batch complete: {success} success, {failed} failed, {total_stored} total insights stored")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
