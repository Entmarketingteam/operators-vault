#!/usr/bin/env python3
"""
Local video processor using Supabase REST API (no psycopg2 needed).
Bypasses YouTube IP blocking by running locally.

Usage:
    python local_rest_processor.py              # process all unprocessed
    python local_rest_processor.py VIDEO_ID     # process one specific video
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

# Load .env
ROOT = Path(__file__).resolve().parent
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip():
                os.environ.setdefault(k.strip(), v.strip())

# Add project root to path for imports
sys.path.insert(0, str(ROOT))

# Config
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPGRAM_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# Flush print immediately
_print = print
def print(*args, **kwargs):
    kwargs.setdefault("flush", True)
    _print(*args, **kwargs)

_headers = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}


# ── Supabase REST helpers ──────────────────────────────────────────────

def sb_get(table: str, params: dict | None = None) -> list[dict]:
    r = httpx.get(f"{SB_URL}/rest/v1/{table}", headers=_headers, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_insert(table: str, data: dict | list, *, upsert: bool = False, returning: bool = True) -> list[dict]:
    h = dict(_headers)
    prefs = []
    if returning:
        prefs.append("return=representation")
    if upsert:
        prefs.append("resolution=merge-duplicates")
    if prefs:
        h["Prefer"] = ", ".join(prefs)
    body = data if isinstance(data, list) else [data]
    r = httpx.post(f"{SB_URL}/rest/v1/{table}", headers=h, json=body, timeout=60)
    r.raise_for_status()
    return r.json() if returning else []


def sb_delete(table: str, params: dict) -> None:
    r = httpx.delete(f"{SB_URL}/rest/v1/{table}", headers=_headers, params=params, timeout=30)
    r.raise_for_status()


# ── Get unprocessed videos ─────────────────────────────────────────────

def get_unprocessed() -> list[dict]:
    """Return videos with no transcription."""
    vids = sb_get("videos", {"select": "video_id,podcast,title", "order": "published_at.desc.nullslast"})
    trans = sb_get("transcriptions", {"select": "video_id"})
    done = {t["video_id"] for t in trans}
    return [v for v in vids if v["video_id"] not in done]


# ── Transcript fetching (local, no IP block) ───────────────────────────

_last_yt_fetch = 0.0

def fetch_transcript_local(video_id: str) -> dict | None:
    """Fetch YouTube captions locally with rate limiting. Returns Deepgram-shaped dict."""
    import time
    global _last_yt_fetch
    from youtube_transcript_api import YouTubeTranscriptApi

    # Rate limit: wait at least 3 seconds between YouTube requests
    elapsed = time.time() - _last_yt_fetch
    if elapsed < 3:
        time.sleep(3 - elapsed)

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["en"])
        snippets = transcript.snippets
        _last_yt_fetch = time.time()
    except Exception as e:
        _last_yt_fetch = time.time()
        print(f"    [captions] failed: {type(e).__name__}: {e}")
        return None

    if not snippets:
        return None

    full_text = " ".join(s.text.replace("\n", " ").strip() for s in snippets if s.text.strip())
    if not full_text.strip():
        return None

    utterances = []
    for s in snippets:
        text = s.text.replace("\n", " ").strip()
        if text:
            utterances.append({
                "start": s.start,
                "end": s.start + s.duration,
                "transcript": text,
                "speaker": 0,
            })

    return {
        "results": {
            "channels": [{"alternatives": [{"transcript": full_text}]}],
            "utterances": utterances,
        },
        "metadata": {"source": "youtube_captions"},
    }


# ── Text chunking ──────────────────────────────────────────────────────

def chunk_text(text: str, size: int = 6000, overlap: int = 500) -> list[str]:
    out = []
    start = 0
    while start < len(text):
        end = start + size
        out.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return out


def format_timestamped(utterances: list[dict]) -> str:
    lines = []
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


# ── Process one insight (for parallel execution) ──────────────────────

def _api_call_with_retry(fn, *args, max_retries=3, **kwargs):
    """Call an API function with retry on rate limit errors."""
    import time
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e):
                if attempt < max_retries:
                    wait = 15 * (attempt + 1)
                    time.sleep(wait)
                    continue
            raise


def _process_insight(it: dict, timestamped: str, video_id: str, podcast: str) -> dict:
    """Process a single insight: title, timestamps, framework. Returns insert-ready dict."""
    from insight_extractor import extract_timestamps, generate_title, make_framework

    cat = it.get("category") or ""
    ins_title = (it.get("title") or "").strip()
    desc = (it.get("description") or "").strip()

    # Generate title if missing or too long
    if len(ins_title) < 3 or len(ins_title) > 120:
        ins_title = _api_call_with_retry(generate_title, desc or ins_title, prompt_set="operators")

    # Extract timestamps
    start_sec, end_sec = _api_call_with_retry(extract_timestamps, timestamped, desc or ins_title, prompt_set="operators")

    # Framework for framework-type insights
    fw = ""
    if "ramework" in cat or cat == "Frameworks and exercises":
        fw = _api_call_with_retry(make_framework, ins_title or "Framework", it.get("_chunk", ""), prompt_set="operators")

    return {
        "id": str(uuid.uuid4()),
        "video_id": video_id,
        "podcast": podcast,
        "category": cat,
        "title": ins_title,
        "description": desc,
        "start_time_sec": start_sec,
        "end_time_sec": end_sec,
        "framework_markdown": fw or None,
        "source_chunk": (it.get("_chunk") or "")[:8000],
    }


# ── Process one video ──────────────────────────────────────────────────

def process_one(video_id: str, podcast: str, title: str = "") -> bool:
    print(f"\n  Processing: {video_id} ({podcast}) - {title[:60]}")

    # Use YouTube captions directly (fast, no yt-dlp needed locally)
    print("    [transcribe] fetching YouTube captions...")
    dg = fetch_transcript_local(video_id)

    if not dg:
        print(f"    [SKIP] no transcript available for {video_id}")
        return False

    # Extract text
    raw = ""
    try:
        ch = (dg.get("results") or {}).get("channels") or []
        if ch:
            raw = (ch[0]["alternatives"][0].get("transcript") or "").strip()
    except (IndexError, KeyError):
        pass

    utterances = []
    results = dg.get("results") or {}
    for x in results.get("utterances") or []:
        utterances.append({
            "start": x.get("start"),
            "end": x.get("end"),
            "transcript": (x.get("transcript") or "").strip(),
            "speaker": x.get("speaker"),
        })

    if not raw:
        print(f"    [SKIP] empty transcript for {video_id}")
        return False

    print(f"    [transcribe] {len(raw)} chars, {len(utterances)} segments")

    # 2) Store transcription
    sb_delete("transcriptions", {"video_id": f"eq.{video_id}"})
    rows = sb_insert("transcriptions", {"video_id": video_id, "raw_text": raw})
    trans_id = rows[0]["id"]
    print(f"    [db] stored transcription {trans_id}")

    # Store segments in bulk
    if utterances:
        seg_batch = []
        for u in utterances:
            st, et = u.get("start"), u.get("end")
            if st is not None and et is not None:
                seg_batch.append({
                    "transcription_id": trans_id,
                    "start_time_sec": float(st),
                    "end_time_sec": float(et),
                    "text": (u.get("transcript") or ""),
                    "speaker_label": str(u.get("speaker") or ""),
                })
        if seg_batch:
            for i in range(0, len(seg_batch), 500):
                sb_insert("segments", seg_batch[i:i+500], returning=False)
            print(f"    [db] stored {len(seg_batch)} segments")

    timestamped = format_timestamped(utterances) if utterances else raw

    # 3) Extract insights via Anthropic (chunk extraction is sequential)
    from insight_extractor import extract_insights

    chunks = chunk_text(raw, size=6000, overlap=500)
    all_insights: list[dict] = []
    for i, ch in enumerate(chunks):
        print(f"    [insights] extracting chunk {i+1}/{len(chunks)}...")
        items = extract_insights(ch, prompt_set="operators")
        for it in items:
            it["_chunk"] = ch
            all_insights.append(it)

    print(f"    [insights] {len(all_insights)} raw insights, enriching in parallel...")

    # 4) Process insights in parallel (title, timestamps, framework)
    sb_delete("insights", {"video_id": f"eq.{video_id}"})

    insight_rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_process_insight, it, timestamped, video_id, podcast): j
            for j, it in enumerate(all_insights)
        }
        done = 0
        for future in as_completed(futures):
            try:
                row = future.result()
                insight_rows.append(row)
                done += 1
                if done % 10 == 0 or done == len(all_insights):
                    print(f"    [insights] enriched {done}/{len(all_insights)}")
            except Exception as e:
                done += 1
                print(f"    [insights] error on insight: {type(e).__name__}: {e}")

    # Bulk insert insights
    if insight_rows:
        for i in range(0, len(insight_rows), 50):
            sb_insert("insights", insight_rows[i:i+50], returning=False)
        print(f"    [db] stored {len(insight_rows)} insights")

    print(f"  [DONE] {video_id}: {len(insight_rows)} insights")
    return True


# ── Main ───────────────────────────────────────────────────────────────

def main():
    if not SB_URL or not SB_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        return 1
    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY must be set")
        return 1

    # Single video mode
    if len(sys.argv) > 1:
        vid = sys.argv[1]
        rows = sb_get("videos", {"video_id": f"eq.{vid}", "select": "video_id,podcast,title"})
        if not rows:
            print(f"Video {vid} not found in DB. Processing as 9operators.")
            ok = process_one(vid, "9operators")
        else:
            ok = process_one(rows[0]["video_id"], rows[0]["podcast"], rows[0].get("title", ""))
        return 0 if ok else 1

    # Batch mode: all unprocessed
    unproc = get_unprocessed()
    if not unproc:
        print("No unprocessed videos.")
        return 0

    print(f"Found {len(unproc)} unprocessed videos\n")
    processed = 0
    failed = 0

    for i, v in enumerate(unproc):
        print(f"\n[{i+1}/{len(unproc)}]", end="")
        try:
            ok = process_one(v["video_id"], v["podcast"], v.get("title", ""))
            if ok:
                processed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [ERROR] {v['video_id']}: {type(e).__name__}: {e}")
            failed += 1

    # Retry pass for failed videos (YouTube blocks are often transient)
    if failed > 0:
        import time
        print(f"\n{'='*60}")
        print(f"First pass: {processed} processed, {failed} failed")
        print(f"Waiting 30s before retry pass...")
        time.sleep(30)

        retry_unproc = get_unprocessed()
        if retry_unproc:
            print(f"Retry pass: {len(retry_unproc)} remaining\n")
            retry_ok = 0
            for i, v in enumerate(retry_unproc):
                print(f"\n[RETRY {i+1}/{len(retry_unproc)}]", end="")
                try:
                    ok = process_one(v["video_id"], v["podcast"], v.get("title", ""))
                    if ok:
                        retry_ok += 1
                        processed += 1
                except Exception as e:
                    print(f"  [ERROR] {v['video_id']}: {type(e).__name__}: {e}")
            failed = len(unproc) - processed
            print(f"\nRetry: {retry_ok} additional successes")

    print(f"\n{'='*60}\nFinal: {processed} processed, {failed} failed out of {len(unproc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
