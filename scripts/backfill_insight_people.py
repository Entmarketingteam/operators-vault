"""
Backfill insight_people links from existing transcription segments.

The insight_extractor pipeline populates insight_people via people_extractor,
but this was not run on the existing 2,713 insights. This script does it retroactively.

Strategy:
  - For each video that has insights but no insight_people rows:
    1. Get its segments (with speaker_label)
    2. Match speaker labels to people rows (by name similarity)
    3. Insert insight_people rows for all insights in that video

Run: DATABASE_URL=... python3 scripts/backfill_insight_people.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _name_matches(speaker_label: str, person_name: str) -> bool:
    """Fuzzy match: speaker label like 'SPEAKER_0: John Smith' vs person_name 'John Smith'."""
    # Strip SPEAKER_N: prefix if present
    label = re.sub(r"^SPEAKER_\d+:\s*", "", speaker_label).strip().lower()
    person = person_name.strip().lower()

    if not label or not person:
        return False

    # Exact match
    if label == person:
        return True

    # Last name match (minimum 4 chars to avoid false positives)
    parts = person.split()
    if len(parts) >= 2:
        last = parts[-1]
        if len(last) >= 4 and last in label:
            return True
        first = parts[0]
        if len(first) >= 4 and first in label:
            return True

    return False


def main():
    conn = psycopg2.connect(DB_URL, sslmode="require")
    cur = conn.cursor()

    # Get all people
    cur.execute("SELECT id, name, slug FROM people ORDER BY name")
    all_people = {str(r[0]): {"name": r[1], "slug": r[2]} for r in cur.fetchall()}
    print(f"[INFO] {len(all_people)} people in DB")

    # Get videos that have insights
    cur.execute("""
        SELECT DISTINCT i.video_id, i.podcast
        FROM insights i
        ORDER BY i.video_id
    """)
    all_videos = cur.fetchall()
    print(f"[INFO] {len(all_videos)} videos have insights")

    # Get videos that already have insight_people entries
    cur.execute("""
        SELECT DISTINCT i.video_id
        FROM insights i
        JOIN insight_people ip ON ip.insight_id = i.id
    """)
    already_linked = {r[0] for r in cur.fetchall()}
    print(f"[INFO] {len(already_linked)} videos already have insight_people links")

    to_process = [(v, p) for v, p in all_videos if v not in already_linked]
    print(f"[INFO] {len(to_process)} videos need backfill")

    linked_count = 0
    video_count = 0

    for video_id, podcast in to_process:
        # Get transcription segments for this video
        cur.execute("""
            SELECT DISTINCT ts.speaker_label
            FROM transcriptions t
            JOIN segments ts ON ts.transcription_id = t.id
            WHERE t.video_id = %s AND ts.speaker_label IS NOT NULL AND ts.speaker_label != ''
        """, (video_id,))
        speaker_labels = [r[0] for r in cur.fetchall()]

        if not speaker_labels:
            continue

        # Match speaker labels to people
        speaker_to_person: dict[str, str] = {}  # speaker_label -> person_id
        for label in speaker_labels:
            for person_id, info in all_people.items():
                if _name_matches(label, info["name"]):
                    speaker_to_person[label] = person_id
                    break

        if not speaker_to_person:
            continue

        # Get all insights for this video
        cur.execute("SELECT id FROM insights WHERE video_id = %s", (video_id,))
        insight_ids = [str(r[0]) for r in cur.fetchall()]

        if not insight_ids:
            continue

        # For each insight, link to all matched people (all speakers in the video)
        # This is coarse but correct — finer timestamp matching would require segment alignment
        matched_person_ids = set(speaker_to_person.values())
        inserted = 0
        for ins_id in insight_ids:
            for person_id in matched_person_ids:
                try:
                    cur.execute(
                        """
                        INSERT INTO insight_people (insight_id, person_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (ins_id, person_id),
                    )
                    inserted += cur.rowcount
                except Exception:
                    conn.rollback()
                    continue

        conn.commit()
        linked_count += inserted
        video_count += 1

        if video_count % 5 == 0:
            print(f"  [progress] {video_count}/{len(to_process)} videos | {linked_count} links inserted")

    print(f"\n[DONE] Processed {video_count} videos | {linked_count} insight_people rows inserted")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
