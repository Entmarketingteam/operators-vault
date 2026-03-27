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
    """Returns list of (video_id, title, podcast, 0) for episodes with no insights."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.video_id, v.title, v.podcast, 0
                FROM videos v
                WHERE EXISTS (
                    SELECT 1 FROM transcriptions t
                    JOIN segments s ON s.transcription_id = t.id
                    WHERE t.video_id = v.video_id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM insights i WHERE i.video_id = v.video_id
                )
                ORDER BY v.video_id
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

        log(f"{progress} {video_id} | {podcast} | {title[:55]}")

        # Run with tee to both capture and stream to log
        import io
        output_lines: list[str] = []

        with subprocess.Popen(
            [sys.executable, str(SCRIPT), video_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_DIR),
            bufsize=1,
        ) as proc:
            for line in proc.stdout:  # type: ignore
                line = line.rstrip()
                output_lines.append(line)
                if line.strip():
                    log(f"  {line}")
            proc.wait()
            returncode = proc.returncode

        # Extract stored count from output
        stored = 0
        for line in output_lines:
            if "Stored:" in line and "insights" in line:
                try:
                    stored = int(line.split("Stored:")[1].split("new")[0].strip())
                except Exception:
                    pass

        if returncode == 0:
            success += 1
            total_stored += stored
            log(f"  => OK: {stored} insights stored")
        else:
            failed += 1
            log(f"  => FAILED (exit {returncode})")

        # Small delay to avoid rate limiting
        time.sleep(3)

    log("")
    log(f"{'='*60}")
    log(f"Batch complete: {success} success, {failed} failed, {total_stored} total insights stored")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
