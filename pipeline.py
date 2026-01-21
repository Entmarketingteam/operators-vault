"""
Operators Vault pipeline: seed from CSVs, process videos (audio -> transcribe -> chunk -> extract -> store).
Usage:
  python pipeline.py --seed-csvs
  python pipeline.py --seed-csvs --process-all
  python pipeline.py --process VIDEO_ID [--podcast 9operators|marketing_operator|finance_operators]
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


def _ensure_video(cursor, video_id: str, podcast: str, title: str = "", duration_seconds: int | None = None) -> None:
    cursor.execute(
        """
        INSERT INTO videos (video_id, podcast, title, duration_seconds)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (video_id) DO UPDATE SET
          podcast = EXCLUDED.podcast,
          title = COALESCE(NULLIF(EXCLUDED.title,''), videos.title),
          duration_seconds = COALESCE(EXCLUDED.duration_seconds, videos.duration_seconds),
          updated_at = now()
        """,
        (video_id, podcast, title or "", duration_seconds),
    )


def _seed_csvs(cursor) -> int:
    from youtube_client import load_all_seed_csvs

    rows = load_all_seed_csvs()
    for r in rows:
        _ensure_video(
            cursor,
            r["video_id"],
            r["podcast"],
            r.get("title") or "",
            r.get("duration_seconds"),
        )
    return len(rows)


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Operators Vault: seed CSVs, process videos (audio->transcribe->extract->store)")
    ap.add_argument("--seed-csvs", action="store_true", help="Load CSVs and upsert into videos")
    ap.add_argument("--process-all", action="store_true", help="After --seed-csvs, process each video (audio->transcribe->extract->store)")
    ap.add_argument("--process", metavar="VIDEO_ID", help="Process one video: download audio, transcribe, extract insights, store")
    ap.add_argument("--podcast", default="9operators", choices=("9operators", "marketing_operator", "finance_operators"), help="For --process when video not in DB")
    ap.add_argument("--work-dir", default=None, help="Temp dir for audio (default: TEMP)")
    ap.add_argument("--prompt-set", default="operators", help="Prompt set under prompts/ (default: operators)")
    args = ap.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else None
    db_url = os.environ.get("DATABASE_URL")

    if args.seed_csvs:
        if not db_url:
            print("DATABASE_URL not set; cannot seed.", flush=True)
            return 1
        import psycopg2

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        n = _seed_csvs(cur)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Seeded {n} videos.", flush=True)

        if args.process_all:
            from youtube_client import load_all_seed_csvs

            rows = load_all_seed_csvs()
            for i, r in enumerate(rows):
                print(f"[{i+1}/{len(rows)}] {r['video_id']} ({r['podcast']})", flush=True)
                _process_one(r["video_id"], r["podcast"], work_dir=work_dir, prompt_set=args.prompt_set)
        return 0

    if args.process:
        ok = _process_one(args.process, args.podcast, work_dir=work_dir, prompt_set=args.prompt_set)
        return 0 if ok else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
