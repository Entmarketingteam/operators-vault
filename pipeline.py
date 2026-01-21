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
) -> None:
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


def _fetch_new(cursor, *, max_per_channel: int = 50, min_duration_sec: int = 300) -> int:
    """Fetch recent videos from YouTube channels (Operators9, MarketingOperators, FinanceOperators) and upsert into videos. Requires YOUTUBE_API_KEY."""
    from youtube_client import fetch_channel_videos, get_channel_handle, resolve_channel_id

    total = 0
    for podcast in ("9operators", "marketing_operator", "finance_operators"):
        handle = get_channel_handle(podcast)
        if not handle:
            continue
        cid = resolve_channel_id(handle)
        if not cid:
            print(f"  [fetch-new] {podcast}: could not resolve @{handle}", flush=True)
            continue
        videos = fetch_channel_videos(cid, podcast=podcast, max_results=max_per_channel)
        n = 0
        for v in videos:
            dur = v.get("duration_seconds")
            if dur is not None and dur < min_duration_sec:
                continue
            _ensure_video(
                cursor,
                v["video_id"],
                v["podcast"],
                v.get("title") or "",
                dur,
                channel_id=v.get("channel_id"),
                published_at=v.get("published_at"),
            )
            n += 1
            total += 1
        print(f"  [fetch-new] {podcast}: {n} upserted (from {len(videos)} fetched)", flush=True)
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
    from deepgram_client import get_raw_text, get_utterances, transcribe
    from insight_extractor import (
        extract_insights,
        extract_timestamps,
        generate_title,
        make_framework,
    )

    work_dir = work_dir or Path(os.environ.get("TEMP", "/tmp"))
    # 1) Ensure video in DB
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        _ensure_video(cur, video_id, podcast, "", None)
        conn.commit()
        cur.close()
        conn.close()

    # 2) Audio
    print(f"  [audio] {video_id}", flush=True)
    path = download_audio(video_id, work_dir)
    if not path:
        print("  [audio] download failed", flush=True)
        return False

    # 3) Transcribe
    print(f"  [transcribe] {video_id}", flush=True)
    dg = transcribe(path, punctuate=True, utterances=True, diarize=True)
    raw = get_raw_text(dg)
    utterances = get_utterances(dg)
    if not raw:
        print("  [transcribe] empty", flush=True)
        return False

    timestamped = _format_timestamped(utterances) if utterances else raw

    # 4) Store transcription (and optionally segments)
    if db_url:
        import psycopg2

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("DELETE FROM transcriptions WHERE video_id = %s", (video_id,))
        cur.execute(
            "INSERT INTO transcriptions (video_id, raw_text) VALUES (%s, %s) RETURNING id",
            (video_id, raw),
        )
        trans_id = cur.fetchone()[0]
        for u in utterances:
            st, et = u.get("start"), u.get("end")
            if st is not None and et is not None:
                cur.execute(
                    "INSERT INTO segments (transcription_id, start_time_sec, end_time_sec, text, speaker_label) VALUES (%s,%s,%s,%s,%s)",
                    (trans_id, float(st), float(et), (u.get("transcript") or ""), str(u.get("speaker") or "")),
                )
        conn.commit()

    # 5) Chunk and extract insights
    chunks = _chunk_text(raw, size=6000, overlap=500)
    all_insights: list[dict] = []
    for i, ch in enumerate(chunks):
        print(f"  [insights] chunk {i+1}/{len(chunks)}", flush=True)
        items = extract_insights(ch, prompt_set=prompt_set)
        for it in items:
            it["_chunk"] = ch
            all_insights.append(it)

    # 6) For each: title, timestamps, framework (if Frameworks and exercises); insert; Meilisearch
    ms_host = os.environ.get("MEILISEARCH_HOST")
    ms_key = os.environ.get("MEILISEARCH_API_KEY")
    ms_client = None
    if ms_host and ms_key:
        try:
            from meilisearch import Client as MeiliClient

            ms_client = MeiliClient(ms_host, ms_key)
            idx = ms_client.index("operators_insights")
            try:
                idx.update_filterable_attributes(["podcast", "category", "video_id"])
                idx.update_searchable_attributes(["title", "description", "framework_markdown"])
                idx.update_sortable_attributes(["start_time_sec", "title", "category"])
            except Exception:
                pass
        except Exception:
            ms_client = None

    if db_url:
        import psycopg2

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("DELETE FROM insights WHERE video_id = %s", (video_id,))
    else:
        conn = None
        cur = None

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
        if cur:
            cur.execute(
                """
                INSERT INTO insights (id, video_id, podcast, category, title, description, start_time_sec, end_time_sec, framework_markdown, source_chunk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ins_id, video_id, podcast, cat, title, desc, start_sec, end_sec, fw or None, (it.get("_chunk") or "")[:8000]),
            )
        if ms_client:
            doc = {
                "id": ins_id,
                "video_id": video_id,
                "podcast": podcast,
                "category": cat,
                "title": title,
                "description": desc,
                "start_time_sec": start_sec,
                "end_time_sec": end_sec,
                "framework_markdown": fw or None,
            }
            try:
                ms_client.index("operators_insights").add_documents([doc])
            except Exception:
                pass

    if conn:
        conn.commit()
        cur.close()
        conn.close()

    print(f"  [done] {video_id} insights={len(all_insights)}", flush=True)
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

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
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
        ok = _process_one(vid, pod, work_dir=work_dir, prompt_set=prompt_set)
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
    ap.add_argument("--podcast", default="9operators", choices=("9operators", "marketing_operator", "finance_operators"), help="For --process when video not in DB")
    ap.add_argument("--fetch-new", action="store_true", help="Fetch new videos from YouTube channels (9 Operators, Marketing, Finance) and upsert into videos. Requires YOUTUBE_API_KEY.")
    ap.add_argument("--process-new", action="store_true", help="Process videos that have no transcription yet (audio->transcribe->extract->store)")
    ap.add_argument("--work-dir", default=None, help="Temp dir for audio (default: TEMP)")
    ap.add_argument("--prompt-set", default="operators", help="Prompt set under prompts/ (default: operators)")
    args = ap.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else None
    db_url = os.environ.get("DATABASE_URL")

    if args.seed_csvs_to_db:
        if not db_url:
            print("DATABASE_URL not set; cannot seed-csvs-to-db.", flush=True)
            return 1
        import psycopg2
        conn = psycopg2.connect(db_url)
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
        conn = psycopg2.connect(db_url)
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

        conn = psycopg2.connect(db_url)
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

        conn = psycopg2.connect(db_url)
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

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        rows = _get_unprocessed(cur)
        cur.close()
        conn.close()
        if not rows:
            print("No unprocessed videos.", flush=True)
            return 0
        for i, (vid, pod) in enumerate(rows):
            print(f"[{i+1}/{len(rows)}] {vid} ({pod})", flush=True)
            _process_one(vid, pod, work_dir=work_dir, prompt_set=args.prompt_set)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
