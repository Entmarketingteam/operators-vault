"""
Backfill insight extraction for videos that have transcriptions but no insights.
Reads transcript from DB, runs the full insights pipeline (extract -> title -> timestamps
-> framework -> companies -> people -> visual moments), writes back to DB.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

from pipeline import _chunk_text, _format_timestamped
from insight_extractor import extract_insights, generate_title, extract_timestamps, make_framework
from company_extractor import extract_companies_from_text, link_insights_to_companies, link_video_to_companies
from people_extractor import extract_people_from_segments, link_insights_to_people
from visual_extractor import extract_visual_moments

def _db_url() -> str:
    """Force Supabase transaction pooler (6543); session mode (5432) caps clients -> EMAXCONNSESSION."""
    url = os.environ["DATABASE_URL"]
    if "pooler.supabase.com" in url and ":5432" in url:
        url = url.replace(":5432", ":6543")
    return url


DB_URL = _db_url()


def get_videos_missing_insights(cur) -> list[tuple[str, str, str | None]]:
    cur.execute("""
        SELECT DISTINCT v.video_id, v.podcast, v.title
        FROM videos v
        JOIN transcriptions t ON t.video_id = v.video_id
        WHERE NOT EXISTS (SELECT 1 FROM insights i WHERE i.video_id = v.video_id)
        ORDER BY v.podcast, v.video_id
    """)
    return cur.fetchall()


def get_transcription(cur, video_id: str) -> tuple[str | None, list[dict]]:
    """Return (raw_text, segments) for the most recent transcription of a video."""
    cur.execute("""
        SELECT id, raw_text FROM transcriptions
        WHERE video_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (video_id,))
    row = cur.fetchone()
    if not row:
        return None, []
    trans_id, raw_text = row

    cur.execute("""
        SELECT start_time_sec, end_time_sec, text, speaker_label
        FROM segments WHERE transcription_id = %s
        ORDER BY start_time_sec
    """, (trans_id,))
    segments = [
        {"start": r[0], "end": r[1], "transcript": r[2], "speaker": r[3]}
        for r in cur.fetchall()
    ]
    return raw_text, segments


def backfill_video(video_id: str, podcast: str, title: str | None, prompt_set: str = "operators") -> bool:
    print(f"\n[backfill] {video_id} ({podcast}) — {title or 'no title'}", flush=True)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    try:
        raw, segments = get_transcription(cur, video_id)
        if not raw:
            print(f"  [skip] no transcription found", flush=True)
            return False

        print(f"  [transcript] {len(raw)} chars, {len(segments)} segments", flush=True)

        timestamped = _format_timestamped(segments) if segments else raw

        # --- Insight extraction ---
        chunks = _chunk_text(raw, size=6000, overlap=500)
        all_insights: list[dict] = []
        for i, ch in enumerate(chunks):
            print(f"  [insights] chunk {i+1}/{len(chunks)}", flush=True)
            items = extract_insights(ch, prompt_set=prompt_set)
            for it in items:
                it["_chunk"] = ch
                all_insights.append(it)

        print(f"  [insights] extracted {len(all_insights)} total", flush=True)

        # --- Clear old insights (in case of partial previous run) ---
        cur.execute("DELETE FROM insights WHERE video_id = %s", (video_id,))

        # --- People extraction from segments ---
        speaker_to_id = extract_people_from_segments(cur, video_id)

        # --- Store each insight ---
        insight_ids: list[str] = []
        for j, it in enumerate(all_insights):
            cat = it.get("category") or ""
            title_str = (it.get("title") or "").strip()
            desc = (it.get("description") or "").strip()

            if len(title_str) < 3:
                title_str = generate_title(desc or title_str, prompt_set=prompt_set)
            elif len(title_str) > 120:
                title_str = generate_title(desc or title_str, prompt_set=prompt_set)

            start_sec, end_sec = extract_timestamps(timestamped, desc or title_str, prompt_set=prompt_set)

            fw = ""
            if "ramework" in cat or cat == "Frameworks and exercises":
                fw = make_framework(title_str or "Framework", it.get("_chunk", ""), prompt_set=prompt_set)

            ins_id = str(uuid.uuid4())
            insight_ids.append(ins_id)
            cur.execute(
                """
                INSERT INTO insights (id, video_id, podcast, category, title, description,
                                      start_time_sec, end_time_sec, framework_markdown, source_chunk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ins_id, video_id, podcast, cat, title_str, desc,
                 start_sec, end_sec, fw or None, (it.get("_chunk") or "")[:8000]),
            )
            companies = extract_companies_from_text(f"{title_str} {desc}")
            if companies:
                link_insights_to_companies(cur, ins_id, companies)

        # --- People links ---
        if speaker_to_id:
            link_insights_to_people(cur, video_id, speaker_to_id)

        # --- Video-level company links ---
        cur.execute("SELECT title, description FROM videos WHERE video_id = %s", (video_id,))
        vrow = cur.fetchone()
        if vrow and (vrow[0] or vrow[1]):
            video_text = f"{vrow[0] or ''} {vrow[1] or ''}"
            companies = extract_companies_from_text(video_text)
            if companies:
                link_video_to_companies(cur, video_id, companies)

        # --- Visual moments ---
        cur.execute("DELETE FROM visual_moments WHERE video_id = %s", (video_id,))
        visuals = extract_visual_moments(raw, timestamped)
        for v in visuals:
            cur.execute(
                """
                INSERT INTO visual_moments (video_id, podcast, start_time_sec, end_time_sec,
                                            description, transcript_excerpt)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (video_id, podcast, v["start_time_sec"], v.get("end_time_sec"),
                 v.get("description", "")[:500], v.get("transcript_excerpt", "")[:1000]),
            )

        conn.commit()
        print(f"  [done] {video_id} insights={len(all_insights)}", flush=True)
        return True
    finally:
        cur.close()
        conn.close()


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    videos = get_videos_missing_insights(cur)
    cur.close()
    conn.close()

    if not videos:
        print("No videos missing insights. Nothing to do.")
        return

    print(f"Found {len(videos)} videos missing insights:")
    for v in videos:
        print(f"  [{v[1]}] {v[0]} — {v[2] or 'no title'}")

    ok = 0
    for video_id, podcast, title in videos:
        try:
            if backfill_video(video_id, podcast, title):
                ok += 1
        except Exception as e:
            print(f"  [error] {video_id}: {e}", flush=True)

    print(f"\nBackfill complete: {ok}/{len(videos)} succeeded.")


if __name__ == "__main__":
    main()
