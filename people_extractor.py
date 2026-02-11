"""
Extract people from segments (speaker_label) and populate people table.
Also link insights to people when speaker matches (for quotes, frameworks by person).
"""
from __future__ import annotations

import re
from typing import Any


def _slugify(name: str) -> str:
    """Convert name to URL slug."""
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def extract_people_from_segments(cursor, video_id: str) -> dict[str, str]:
    """
    Extract unique speakers from segments for a video. Returns {speaker_label: person_id}.
    Creates people records if missing, generates slugs.
    """
    cursor.execute(
        """
        SELECT DISTINCT speaker_label
        FROM segments s
        JOIN transcriptions t ON t.id = s.transcription_id
        WHERE t.video_id = %s AND speaker_label IS NOT NULL AND speaker_label != ''
        """,
        (video_id,),
    )
    speakers = [r[0] for r in cursor.fetchall()]
    speaker_to_id: dict[str, str] = {}
    for speaker in speakers:
        if not speaker or len(speaker.strip()) < 2:
            continue
        name = speaker.strip()
        slug = _slugify(name)
        # Find or create person
        cursor.execute("SELECT id FROM people WHERE name = %s", (name,))
        row = cursor.fetchone()
        if row:
            person_id = str(row[0])
        else:
            cursor.execute(
                "INSERT INTO people (name, slug) VALUES (%s, %s) RETURNING id",
                (name, slug),
            )
            person_id = str(cursor.fetchone()[0])
        speaker_to_id[speaker] = person_id
        # Link to video
        cursor.execute(
            """
            INSERT INTO video_people (video_id, person_id)
            VALUES (%s, %s)
            ON CONFLICT (video_id, person_id) DO NOTHING
            """,
            (video_id, person_id),
        )
    return speaker_to_id


def link_insights_to_people(cursor, video_id: str, speaker_to_id: dict[str, str]) -> None:
    """
    Link insights to people based on speaker_label from segments at the same timestamp.
    For quotes, link to the speaker; for other insights, link if speaker_label matches.
    """
    if not speaker_to_id:
        return
    # Get insights with timestamps
    cursor.execute(
        """
        SELECT id, start_time_sec, category
        FROM insights
        WHERE video_id = %s AND start_time_sec IS NOT NULL
        """,
        (video_id,),
    )
    insights = cursor.fetchall()
    for ins_id, start_sec, category in insights:
        # Find segments at this timestamp (within 5 seconds)
        cursor.execute(
            """
            SELECT DISTINCT speaker_label
            FROM segments s
            JOIN transcriptions t ON t.id = s.transcription_id
            WHERE t.video_id = %s
              AND ABS(s.start_time_sec - %s) < 5
              AND speaker_label IS NOT NULL AND speaker_label != ''
            LIMIT 1
            """,
            (video_id, float(start_sec)),
        )
        row = cursor.fetchone()
        if row and row[0] in speaker_to_id:
            person_id = speaker_to_id[row[0]]
            # Link insight to person (especially for Quotes)
            cursor.execute(
                """
                INSERT INTO insight_people (insight_id, person_id)
                VALUES (%s, %s)
                ON CONFLICT (insight_id, person_id) DO NOTHING
                """,
                (ins_id, person_id),
            )
