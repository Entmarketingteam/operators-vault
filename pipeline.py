"""
Operators Vault pipeline: seed from CSVs or seed_links (Supabase), process videos (audio -> transcribe -> chunk -> extract -> store).
Usage:
  python pipeline.py --seed-csvs
  python pipeline.py --seed-csvs --process-all
  python pipeline.py --seed-csvs-to-db        # CSVs -> seed_links (Supabase)
  python pipeline.py --seed-from-db [--process-all]   # seed_links -> videos; with --process-all then process unprocessed
  python pipeline.py --process VIDEO_ID [--podcast 9operators|marketing_operator|finance_operators]
  python pipeline.py --fetch-new              # fetch new videos from YouTube channels, upsert to videos
  python pipeline.py --process-new            # process videos that have no transcription yet
  python pipeline.py --fetch-new --process-new
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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

import db_utils
from structured_logger import get_logger

_log = get_logger("pipeline")


def _plog(msg: str) -> None:
    """Legacy log helper — now delegates to structured logger."""
    _log.info(msg.strip())


def _chunk_text(text: str, size: int = 6000, overlap: int = 500) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        out.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return out


def _format_timestamped(utterances: list[dict]) -> str:
    lines: list[str] = []
    for u in utterances:
        s = u.get("start")
        if s is None:
            continue
        h = int(s) // 3600
        m = (int(s) % 3600) // 60
        sec = int(s) % 60
        ts = f"{h:02d}:{m:02d}:{sec:02d}"
        sp = u.get("speaker") or "Speaker"
        t = (u.get("transcript") or "").strip()
        if t:
            lines.append(f"{ts} {sp}: {t}")
    return "\n".join(lines)


def _ensure_video(
    cursor,
    video_id: str,
    podcast: str,
    title: str = "",
    duration_seconds: int | None = None,
    channel_id: str | None = None,
    published_at: str | None = None,
    *,
    view_count: int | None = None,
    like_count: int | None = None,
    comment_count: int | None = None,
    thumbnail_url: str | None = None,
    description: str | None = None,
    channel_title: str | None = None,
    tags: str | None = None,
) -> None:
    import psycopg2
    try:
        cursor.execute(
            """
            INSERT INTO videos (
                video_id, podcast, title, duration_seconds, channel_id, published_at,
                view_count, like_count, comment_count, thumbnail_url, description, channel_title, tags
            )
            VALUES (%s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
              podcast = EXCLUDED.podcast,
              title = COALESCE(NULLIF(EXCLUDED.title,''), videos.title),
              duration_seconds = COALESCE(EXCLUDED.duration_seconds, videos.duration_seconds),
              channel_id = COALESCE(EXCLUDED.channel_id, videos.channel_id),
              published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
              view_count = COALESCE(EXCLUDED.view_count, videos.view_count),
              like_count = COALESCE(EXCLUDED.like_count, videos.like_count),
              comment_count = COALESCE(EXCLUDED.comment_count, videos.comment_count),
              thumbnail_url = COALESCE(EXCLUDED.thumbnail_url, videos.thumbnail_url),
              description = COALESCE(EXCLUDED.description, videos.description),
              channel_title = COALESCE(EXCLUDED.channel_title, videos.channel_title),
              tags = COALESCE(EXCLUDED.tags, videos.tags),
              updated_at = now()
            """,
            (
                video_id, podcast, title or "", duration_seconds, channel_id, published_at,
                view_count, like_count, comment_count, thumbnail_url, description, channel_title, tags,
            ),
        )
    except psycopg2.ProgrammingError as e:
        if "does not exist" in str(e) or "column" in str(e).lower():
            # Minimal schema (no view_count, like_count, etc.): upsert only base columns.
            # Use a fresh connection for the fallback — the rollback on a pooler-closed
            # connection raises "SSL connection has been closed unexpectedly" which masks
            # the real ProgrammingError and prevents the fallback from executing.
            try:
                cursor.connection.rollback()
            except Exception:
                pass  # Connection may already be dead; ignore rollback failure
            try:
                cursor.execute(
                    """
                    INSERT INTO videos (video_id, podcast, title, duration_seconds, channel_id, published_at)
                    VALUES (%s, %s, %s, %s, %s, %s::timestamptz)
                    ON CONFLICT (video_id) DO UPDATE SET
                      podcast = EXCLUDED.podcast,
                      title = COALESCE(NULLIF(EXCLUDED.title,''), videos.title),
                      duration_seconds = COALESCE(EXCLUDED.duration_seconds, videos.duration_seconds),
                      channel_id = COALESCE(EXCLUDED.channel_id, videos.channel_id),
                      published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
                      updated_at = now()
                    """,
                    (video_id, podcast, title or "", duration_seconds, channel_id, published_at),
                )
            except Exception:
                # Connection is completely dead — open a fresh one and retry
                _db_url = db_utils.resolve_db_url() or ""
                if not _db_url:
                    raise
                _fresh_conn = db_utils.connect(_db_url)
                _fresh_cur = _fresh_conn.cursor()
                _fresh_cur.execute(
                    """
                    INSERT INTO videos (video_id, podcast, title, duration_seconds, channel_id, published_at)
                    VALUES (%s, %s, %s, %s, %s, %s::timestamptz)
                    ON CONFLICT (video_id) DO UPDATE SET
                      podcast = EXCLUDED.podcast,
                      title = COALESCE(NULLIF(EXCLUDED.title,''), videos.title),
                      duration_seconds = COALESCE(EXCLUDED.duration_seconds, videos.duration_seconds),
                      channel_id = COALESCE(EXCLUDED.channel_id, videos.channel_id),
                      published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
                      updated_at = now()
                    """,
                    (video_id, podcast, title or "", duration_seconds, channel_id, published_at),
                )
                _fresh_conn.commit()
                _fresh_cur.close()
                _fresh_conn.close()
        else:
            raise


def _seed_csvs(cursor, paths_override: dict[str, str] | None = None) -> int:
    from youtube_client import load_all_seed_csvs

    rows = load_all_seed_csvs(paths=paths_override)
    for r in rows:
        _ensure_video(
            cursor,
            r["video_id"],
            r["podcast"],
            r.get("title") or "",
            r.get("duration_seconds"),
        )
    return len(rows)


def upsert_seed_links(cursor, rows: list[dict]) -> int:
    """
    Upsert into seed_links. Each row: video_id, podcast, title?, duration_seconds?, url?.
    Returns number of rows upserted. ON CONFLICT (video_id, podcast) DO UPDATE.
    """
    n = 0
    for r in rows:
        vid = (r.get("video_id") or "").strip()
        pod = (r.get("podcast") or "").strip()
        if not vid or not pod:
            continue
        cursor.execute(
            """
            INSERT INTO seed_links (video_id, podcast, title, duration_seconds, url)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (video_id, podcast) DO UPDATE SET
              title = COALESCE(NULLIF(EXCLUDED.title,''), seed_links.title),
              duration_seconds = COALESCE(EXCLUDED.duration_seconds, seed_links.duration_seconds),
              url = COALESCE(NULLIF(EXCLUDED.url,''), seed_links.url),
              updated_at = now()
            """,
            (
                vid,
                pod,
                (r.get("title") or "")[:2048] if r.get("title") else "",
                r.get("duration_seconds"),
                (r.get("url") or "")[:2048] if r.get("url") else "",
            ),
        )
        n += 1
    return n


def _seed_from_db(cursor) -> int:
    """Upsert from seed_links into videos. Returns number of rows upserted."""
    cursor.execute("SELECT video_id, podcast, title, duration_seconds FROM seed_links")
    rows = cursor.fetchall()
    for r in rows:
        _ensure_video(cursor, r[0], r[1], r[2] or "", r[3])
    return len(rows)


def _seed_csvs_to_db(cursor, paths_override: dict[str, str] | None = None) -> int:
    """Load CSVs and upsert into seed_links. Returns number upserted."""
    from youtube_client import load_all_seed_csvs

    rows = load_all_seed_csvs(paths=paths_override)
    return upsert_seed_links(cursor, rows)


def _ensure_video_from_record(cursor, v: dict, min_duration_sec: int = 300) -> bool:
    """Upsert one video from a fetch record (channel or playlist). Returns True if upserted."""
    dur = v.get("duration_seconds")
    if dur is not None and dur < min_duration_sec:
        return False
    _ensure_video(
        cursor,
        v["video_id"],
        v["podcast"],
        v.get("title") or "",
        dur,
        channel_id=v.get("channel_id"),
        published_at=v.get("published_at"),
        view_count=v.get("view_count"),
        like_count=v.get("like_count"),
        comment_count=v.get("comment_count"),
        thumbnail_url=v.get("thumbnail_url"),
        description=v.get("description"),
        channel_title=v.get("channel_title"),
        tags=v.get("tags"),
    )
    return True


def _load_channel_configs_from_db() -> dict[str, str]:
    """
    Load active channel configs from channel_configs table.
    Returns {slug: channel_handle} dict.
    Falls back to DEFAULT_CHANNEL_HANDLES from youtube_client on any error.
    """
    from youtube_client import DEFAULT_CHANNEL_HANDLES
    try:
        import psycopg2
        db_url = db_utils.resolve_db_url() or ""
        if not db_url:
            return dict(DEFAULT_CHANNEL_HANDLES)
        conn = db_utils.connect(db_url)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, channel_handle FROM channel_configs WHERE active = TRUE ORDER BY created_at"
            )
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return dict(DEFAULT_CHANNEL_HANDLES)
        return {slug: handle for slug, handle in rows}
    except Exception as e:
        _log.warning("channel_configs_load_failed — using hardcoded defaults: %s", e)
        from youtube_client import DEFAULT_CHANNEL_HANDLES
        return dict(DEFAULT_CHANNEL_HANDLES)


def _fetch_new(cursor, *, max_per_channel: int = 50, min_duration_sec: int = 300) -> int:
    """Fetch recent videos from YouTube (channels from DB + TITANS playlist) and upsert into videos. Requires YOUTUBE_API_KEY."""
    from youtube_client import (
        fetch_channel_videos,
        fetch_playlist_videos,
        get_playlist_id,
        resolve_channel_id,
    )

    # Load channels from DB (falls back to hardcoded if DB unavailable)
    channel_map = _load_channel_configs_from_db()

    total = 0
    for podcast, handle in channel_map.items():
        if not handle:
            continue
        cid = resolve_channel_id(handle)
        if not cid:
            print(f"  [fetch-new] {podcast}: could not resolve @{handle}", flush=True)
            continue
        videos = fetch_channel_videos(cid, podcast=podcast, max_results=max_per_channel)
        n = 0
        for v in videos:
            if _ensure_video_from_record(cursor, v, min_duration_sec):
                n += 1
                total += 1
        print(f"  [fetch-new] {podcast}: {n} upserted (from {len(videos)} fetched)", flush=True)

    # TITANS: fetch by playlist when YOUTUBE_PLAYLIST_TITANS is set
    playlist_id = get_playlist_id("titans")
    if playlist_id:
        videos = fetch_playlist_videos(playlist_id, podcast="titans", max_results=max_per_channel)
        n = 0
        for v in videos:
            if _ensure_video_from_record(cursor, v, min_duration_sec):
                n += 1
                total += 1
        print(f"  [fetch-new] titans: {n} upserted (from {len(videos)} fetched)", flush=True)
    else:
        print("  [fetch-new] titans: no YOUTUBE_PLAYLIST_TITANS set, skipping", flush=True)

    return total


def _get_unprocessed(cursor) -> list[tuple[str, str]]:
    """Return (video_id, podcast) for videos that have no transcription yet."""
    cursor.execute(
        """
        SELECT v.video_id, v.podcast FROM videos v
        LEFT JOIN transcriptions t ON t.video_id = v.video_id
        WHERE t.id IS NULL
        ORDER BY v.published_at DESC NULLS LAST, v.created_at DESC
        """
    )
    return [(r[0], r[1]) for r in cursor.fetchall()]


def _process_one(
    video_id: str,
    podcast: str,
    *,
    work_dir: Path | None = None,
    prompt_set: str = "operators",
) -> bool:
    import uuid

    from audio_extractor import download_audio
    from deepgram_client import DeepgramAuthError, get_raw_text, get_utterances, transcribe
    from insight_extractor import (
        extract_insights,
        extract_timestamps,
        generate_title,
        make_framework,
    )

    work_dir = work_dir or Path(os.environ.get("TEMP", "/tmp"))
    # 1) Ensure video in DB
    db_url = db_utils.resolve_db_url()
    if db_url:
        import psycopg2

        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        _ensure_video(cur, video_id, podcast, "", None)
        conn.commit()
        cur.close()
        conn.close()

    # 2) Audio + Transcription
    #    Try yt-dlp audio download → Deepgram first.
    #    If audio download is blocked (datacenter IP), fall back to YouTube
    #    auto-generated captions which bypass the block entirely.
    _plog(f"  [audio] {video_id}")
    path, err = download_audio(video_id, work_dir)

    dg = None
    transcript_source = "deepgram"

    if path:
        # 3a) Transcribe via Deepgram (DeepgramAuthError propagates to abort the batch)
        _plog(f"  [transcribe] {video_id}")
        try:
            dg = transcribe(path, punctuate=True, utterances=True, diarize=True)
        except DeepgramAuthError:
            _plog(f"  [transcribe] FATAL: Deepgram API key is invalid — aborting")
            raise
    else:
        _plog(f"  [audio] download failed for {video_id}: err={repr(err)}")

    # 3b) Fallback: YouTube captions (works from datacenter IPs)
    if dg is None or not get_raw_text(dg):
        from youtube_transcript import fetch_transcript, is_available
        if is_available():
            _plog(f"  [yt-captions] trying YouTube captions fallback for {video_id}")
            dg = fetch_transcript(video_id)
            if dg and get_raw_text(dg):
                transcript_source = "youtube_captions"
                _plog(f"  [yt-captions] success for {video_id}")
            else:
                _plog(f"  [yt-captions] no captions available for {video_id}")
                dg = None
        else:
            _plog(f"  [yt-captions] youtube-transcript-api not installed, skipping fallback")

    if dg is None:
        _plog(f"  [transcribe] failed for {video_id}: no audio and no captions available")
        return False
    raw = get_raw_text(dg)
    utterances = get_utterances(dg)
    if not raw:
        _plog(f"  [transcribe] empty transcript for {video_id}: dg keys={list(dg.keys())[:10] if isinstance(dg, dict) else 'not a dict'}")
        return False
    _plog(f"  [transcribe] {video_id} source={transcript_source} len={len(raw)}")

    timestamped = _format_timestamped(utterances) if utterances else raw

    # 4) Store transcription (and optionally segments)
    if db_url:
        import psycopg2

        # Supabase poolers default to a short statement_timeout. Override at
        # session level so multi-hundred-row inserts don't get killed.
        conn = db_utils.connect(db_url, options="-c statement_timeout=600000")
        cur = conn.cursor()
        cur.execute("DELETE FROM transcriptions WHERE video_id = %s", (video_id,))
        cur.execute(
            "INSERT INTO transcriptions (video_id, raw_text) VALUES (%s, %s) RETURNING id",
            (video_id, raw),
        )
        trans_id = cur.fetchone()[0]
        # Commit transcription row immediately so a downstream segments failure
        # doesn't leave us with no transcription at all.
        conn.commit()
        for i, u in enumerate(utterances):
            st, et = u.get("start"), u.get("end")
            if st is not None and et is not None:
                cur.execute(
                    "INSERT INTO segments (transcription_id, start_time_sec, end_time_sec, text, speaker_label) VALUES (%s,%s,%s,%s,%s)",
                    (trans_id, float(st), float(et), (u.get("transcript") or ""), str(u.get("speaker") or "")),
                )
            # Commit every 200 segments to avoid huge transactions
            if (i + 1) % 200 == 0:
                conn.commit()
        conn.commit()
        cur.close()
        conn.close()

    # 5) Chunk and extract insights
    chunks = _chunk_text(raw, size=6000, overlap=500)
    all_insights: list[dict] = []
    for i, ch in enumerate(chunks):
        _plog(f"  [insights] chunk {i+1}/{len(chunks)}")
        items = extract_insights(ch, prompt_set=prompt_set)
        for it in items:
            it["_chunk"] = ch
            all_insights.append(it)

    # 6) For each: title, timestamps, framework; insert into Postgres (FTS indexes auto-update)
    # Phase 2: Import extractors
    if db_url:
        from company_extractor import extract_companies_from_text, link_insights_to_companies, link_video_to_companies
        from people_extractor import extract_people_from_segments, link_insights_to_people
    if db_url:
        import psycopg2

        conn = db_utils.connect(db_url, options="-c statement_timeout=600000")
        cur = conn.cursor()
        cur.execute("DELETE FROM insights WHERE video_id = %s", (video_id,))
        # Phase 2: Extract people from segments
        speaker_to_id = extract_people_from_segments(cur, video_id)
        conn.commit()  # commit deletes + people before bulk insight insert
    else:
        conn = None
        cur = None
        speaker_to_id = {}

    insight_ids: list[str] = []
    for j, it in enumerate(all_insights):
        cat = it.get("category") or ""
        title = (it.get("title") or "").strip()
        desc = (it.get("description") or "").strip()
        # generate title if missing or short
        if len(title) < 3:
            title = generate_title(desc or title, prompt_set=prompt_set)
        elif len(title) > 120:
            title = generate_title(desc or title, prompt_set=prompt_set)
        # timestamps
        start_sec, end_sec = extract_timestamps(timestamped, desc or title, prompt_set=prompt_set)
        # framework for Frameworks and exercises
        fw = ""
        if "ramework" in cat or cat == "Frameworks and exercises":
            fw = make_framework(title or "Framework", it.get("_chunk", ""), prompt_set=prompt_set)
        ins_id = str(uuid.uuid4())
        insight_ids.append(ins_id)
        if cur:
            cur.execute(
                """
                INSERT INTO insights (id, video_id, podcast, category, title, description, start_time_sec, end_time_sec, framework_markdown, source_chunk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ins_id, video_id, podcast, cat, title, desc, start_sec, end_sec, fw or None, (it.get("_chunk") or "")[:8000]),
            )
            # Phase 2: Extract companies from insight text
            if db_url:
                insight_text = f"{title} {desc}"
                companies = extract_companies_from_text(insight_text)
                if companies:
                    link_insights_to_companies(cur, ins_id, companies)
            # Commit each insight individually so a single hung statement
            # only loses one row, not the entire batch.
            if conn and (j + 1) % 25 == 0:
                conn.commit()

    if conn:
        conn.commit()  # commit any remaining insights before downstream stages
        # Phase 2: Link insights to people based on speaker_label
        if speaker_to_id:
            link_insights_to_people(cur, video_id, speaker_to_id)
        # Phase 2: Extract companies from video title/description
        if db_url:
            cur.execute("SELECT title, description FROM videos WHERE video_id = %s", (video_id,))
            vrow = cur.fetchone()
            if vrow and (vrow[0] or vrow[1]):
                video_text = f"{vrow[0] or ''} {vrow[1] or ''}"
                companies = extract_companies_from_text(video_text)
                if companies:
                    link_video_to_companies(cur, video_id, companies)
        # Phase 3: Extract visual moments
        if db_url:
            from visual_extractor import extract_visual_moments
            cur.execute("DELETE FROM visual_moments WHERE video_id = %s", (video_id,))
            visuals = extract_visual_moments(raw, timestamped)
            for v in visuals:
                cur.execute(
                    """
                    INSERT INTO visual_moments (video_id, podcast, start_time_sec, end_time_sec, description, transcript_excerpt)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (video_id, podcast, v["start_time_sec"], v.get("end_time_sec"), v.get("description", "")[:500], v.get("transcript_excerpt", "")[:1000]),
                )
        conn.commit()
        cur.close()
        conn.close()

    _plog(f"  [done] {video_id} insights={len(all_insights)}")
    return True


def run_seed_and_process_all(
    *,
    paths_override: dict[str, str] | None = None,
    seed_link_rows: list[dict] | None = None,
    from_db: bool = False,
    work_dir: Path | None = None,
    prompt_set: str = "operators",
) -> dict:
    """
    Seed then process unprocessed videos. Returns {seeded, processed, video_ids}.
    - seed_link_rows: upsert into seed_links, then seed-from-db and process-new.
    - from_db: seed from seed_links into videos, then process-new.
    - else: seed from CSVs (paths_override or DEFAULT_CSV_PATHS) into videos, then process-new.
    Raises on missing DATABASE_URL.
    """
    import psycopg2

    db_url = db_utils.resolve_db_url()
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    conn = db_utils.connect(db_url)
    cur = conn.cursor()
    seeded: int = 0
    if seed_link_rows:
        upsert_seed_links(cur, seed_link_rows)
        conn.commit()
        seeded = _seed_from_db(cur)
        conn.commit()
    elif from_db:
        seeded = _seed_from_db(cur)
        conn.commit()
    else:
        seeded = _seed_csvs(cur, paths_override=paths_override)
        conn.commit()

    rows = _get_unprocessed(cur)
    cur.close()
    conn.close()

    processed = []
    for vid, pod in rows:
        try:
            ok = _process_one(vid, pod, work_dir=work_dir, prompt_set=prompt_set)
        except Exception as e:
            # Import here to avoid circular dependency at module level
            from deepgram_client import DeepgramAuthError
            if isinstance(e, DeepgramAuthError):
                _log.error("Deepgram auth error — aborting remaining videos: %s", e)
                break
            _log.error("Processing failed for %s: %s", vid, e)
            continue
        if ok:
            processed.append(vid)
    return {"seeded": seeded, "processed": len(processed), "video_ids": processed}


def main() -> int:
    ap = argparse.ArgumentParser(description="Operators Vault: seed CSVs, process videos (audio->transcribe->extract->store)")
    ap.add_argument("--seed-csvs", action="store_true", help="Load CSVs and upsert into videos")
    ap.add_argument("--seed-csvs-to-db", action="store_true", help="Load CSVs and upsert into seed_links (Supabase); does not touch videos")
    ap.add_argument("--seed-from-db", action="store_true", help="Upsert from seed_links into videos; use with --process-new to run backfill from DB")
    ap.add_argument("--process-all", action="store_true", help="After --seed-csvs or --seed-from-db, process unprocessed videos (audio->transcribe->extract->store)")
    ap.add_argument("--process", metavar="VIDEO_ID", help="Process one video: download audio, transcribe, extract insights, store")
    ap.add_argument("--podcast", default="9operators", choices=("9operators", "marketing_operator", "finance_operators", "titans"), help="For --process when video not in DB")
    ap.add_argument("--fetch-new", action="store_true", help="Fetch new videos from YouTube channels (9 Operators, Marketing, Finance) and upsert into videos. Requires YOUTUBE_API_KEY.")
    ap.add_argument("--process-new", action="store_true", help="Process videos that have no transcription yet (audio->transcribe->extract->store)")
    ap.add_argument("--work-dir", default=None, help="Temp dir for audio (default: TEMP)")
    ap.add_argument("--prompt-set", default="operators", help="Prompt set under prompts/ (default: operators)")
    args = ap.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else None
    db_url = db_utils.resolve_db_url()

    if args.seed_csvs_to_db:
        if not db_url:
            print("DATABASE_URL not set; cannot seed-csvs-to-db.", flush=True)
            return 1
        import psycopg2
        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        n = _seed_csvs_to_db(cur, paths_override=None)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Upserted {n} rows into seed_links.", flush=True)
        return 0

    if args.seed_from_db:
        if not db_url:
            print("DATABASE_URL not set; cannot seed-from-db.", flush=True)
            return 1
        if args.process_all:
            out = run_seed_and_process_all(from_db=True, work_dir=work_dir, prompt_set=args.prompt_set)
            print(f"Seeded {out['seeded']} from seed_links; processed {out['processed']}.", flush=True)
            return 0
        import psycopg2
        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        n = _seed_from_db(cur)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Seeded {n} videos from seed_links.", flush=True)
        return 0

    if args.seed_csvs:
        if not db_url:
            print("DATABASE_URL not set; cannot seed.", flush=True)
            return 1
        if args.process_all:
            out = run_seed_and_process_all(paths_override=None, work_dir=work_dir, prompt_set=args.prompt_set)
            print(f"Seeded {out['seeded']} videos; processed {out['processed']}.", flush=True)
            return 0
        import psycopg2

        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        n = _seed_csvs(cur, paths_override=None)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Seeded {n} videos.", flush=True)
        return 0

    if args.process:
        ok = _process_one(args.process, args.podcast, work_dir=work_dir, prompt_set=args.prompt_set)
        return 0 if ok else 1

    if args.fetch_new:
        if not db_url:
            print("DATABASE_URL not set; cannot fetch-new.", flush=True)
            return 1
        if not os.environ.get("YOUTUBE_API_KEY"):
            print("YOUTUBE_API_KEY not set; required for --fetch-new.", flush=True)
            return 1
        import psycopg2

        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        n = _fetch_new(cur)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Fetch-new: {n} videos upserted.", flush=True)
        if not args.process_new:
            return 0

    if args.process_new:
        if not db_url:
            print("DATABASE_URL not set; cannot process-new.", flush=True)
            return 1
        import psycopg2

        conn = db_utils.connect(db_url)
        cur = conn.cursor()
        rows = _get_unprocessed(cur)
        cur.close()
        conn.close()
        if not rows:
            print("No unprocessed videos.", flush=True)
            return 0
        from deepgram_client import DeepgramAuthError
        for i, (vid, pod) in enumerate(rows):
            print(f"[{i+1}/{len(rows)}] {vid} ({pod})", flush=True)
            try:
                _process_one(vid, pod, work_dir=work_dir, prompt_set=args.prompt_set)
            except DeepgramAuthError as e:
                print(f"FATAL: Deepgram API key invalid — aborting. {e}", flush=True)
                return 1
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
