#!/usr/bin/env python3
"""
Extract insights from a single episode's raw transcript segments.
Usage: python extract_episode_insights.py <video_id>
"""
import os
import sys
import json
import re
import urllib.request
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import psycopg2
from insight_extractor import (
    _anthropic_message,
    parse_extract_insights_output,
    _load_prompt,
    _VALID_CATEGORIES,
)

VIDEO_ID = sys.argv[1] if len(sys.argv) > 1 else None
if not VIDEO_ID:
    print("Usage: python extract_episode_insights.py <video_id>")
    sys.exit(1)

DATABASE_URL = os.environ["DATABASE_URL"]
AGENT_SERVER_URL = os.environ.get("AGENT_SERVER_URL", "https://ent-agent-server-production.up.railway.app")
AGENT_SERVER_API_KEY = os.environ.get("AGENT_SERVER_API_KEY", "atxxwpeHyTvCf2AUTD9TZQAExuClU5wX8SVBDfwzAnw")
os.environ["AGENT_SERVER_API_KEY"] = AGENT_SERVER_API_KEY

CHUNK_SIZE = 6000   # characters per chunk sent to LLM
OVERLAP = 500       # overlap between chunks to avoid cutting mid-thought
MAX_CHUNKS = 12     # process up to 12 chunks per episode (~72k chars total)

def get_segments(conn, video_id: str) -> tuple[str, str, str]:
    """Returns (full_text, podcast, episode_title) for the video."""
    with conn.cursor() as cur:
        # Get video metadata
        cur.execute("""
            SELECT v.title, v.podcast
            FROM videos v
            WHERE v.video_id = %s
            LIMIT 1
        """, (video_id,))
        row = cur.fetchone()
        title = row[0] if row else "Unknown"
        podcast = row[1] if row else "unknown"

        # Get segments ordered by start time
        cur.execute("""
            SELECT s.text, s.start_time_sec
            FROM segments s
            JOIN transcriptions t ON t.id = s.transcription_id
            JOIN videos v ON v.video_id = t.video_id
            WHERE v.video_id = %s
            ORDER BY s.start_time_sec ASC
        """, (video_id,))
        rows = cur.fetchall()
        full_text = " ".join(r[0] for r in rows if r[0])

    return full_text, podcast, title


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def extract_from_chunk(chunk: str, episode_title: str, podcast: str, retries: int = 3) -> list[dict]:
    """Send one chunk to LLM and get insights back. Retries on empty/error."""
    import time as _time
    prompt_tpl = _load_prompt("extract_insights_system", "operators")
    if not prompt_tpl:
        return []

    # Inject episode context into the chunk
    enriched = f"Episode: {episode_title} ({podcast})\n\n{chunk}"
    user = prompt_tpl.replace("{transcript}", enriched)
    system = "You are an expert eCommerce and DTC podcast analyst. Follow the instructions exactly. Be thorough — extract 5-15 insights per chunk."

    for attempt in range(retries):
        try:
            raw = _anthropic_message(system, user)
            if raw:
                return parse_extract_insights_output(raw)
        except Exception as e:
            print(f" [retry {attempt+1}/{retries}: {e}]", end="", flush=True)
        if attempt < retries - 1:
            _time.sleep(5 * (attempt + 1))
    return []


def store_insights(db_url: str, video_id: str, podcast: str, insights: list[dict]) -> int:
    """Store insights in the DB, skip duplicates by title. Opens a fresh connection."""
    if not insights:
        return 0

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM insights WHERE video_id = %s", (video_id,))
            existing = {r[0].lower() for r in cur.fetchall()}

            inserted = 0
            for ins in insights:
                t = ins.get("title", "").strip()
                description = ins.get("description", "").strip()
                category = ins.get("category", "").strip()

                if not t or t.lower() in existing:
                    continue
                if category not in _VALID_CATEGORIES:
                    continue

                cur.execute("""
                    INSERT INTO insights (video_id, podcast, category, title, description)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (video_id, podcast, category, t, description))
                existing.add(t.lower())
                inserted += 1

        conn.commit()
        return inserted
    finally:
        conn.close()


def main():
    print(f"\n{'='*60}")
    print(f"Extracting insights for: {VIDEO_ID}")
    print(f"{'='*60}\n")

    conn = psycopg2.connect(DATABASE_URL)
    full_text, podcast, title = get_segments(conn, VIDEO_ID)
    conn.close()

    try:
        print(f"Episode: {title}")
        print(f"Podcast: {podcast}")
        print(f"Text length: {len(full_text):,} chars")

        if not full_text:
            print("ERROR: No segments found")
            sys.exit(1)

        chunks = chunk_text(full_text)
        chunks = chunks[:MAX_CHUNKS]  # cap
        print(f"Processing {len(chunks)} chunks (capped at {MAX_CHUNKS})\n")

        all_insights = []
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...", end="", flush=True)
            insights = extract_from_chunk(chunk, title, podcast)
            print(f" → {len(insights)} insights")
            all_insights.extend(insights)

        # Deduplicate by title
        seen = set()
        unique = []
        for ins in all_insights:
            t = ins.get("title", "").lower()
            if t and t not in seen:
                seen.add(t)
                unique.append(ins)

        print(f"\nTotal raw: {len(all_insights)} | Unique: {len(unique)}")

        # Store (opens a fresh connection — avoids timeout after long LLM loop)
        stored = store_insights(DATABASE_URL, VIDEO_ID, podcast, unique)
        print(f"Stored: {stored} new insights")

        # Summary by category
        cats: dict[str, int] = {}
        for ins in unique:
            c = ins.get("category", "unknown")
            cats[c] = cats.get(c, 0) + 1
        print("\nBy category:")
        for cat, count in sorted(cats.items()):
            print(f"  {cat}: {count}")

        print(f"\n✅ Done: {stored} insights stored for {VIDEO_ID}")
        return stored

    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
