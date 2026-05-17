"""
Backfill videos with Gemini Multimodal extraction.
Iterates through videos (all or specific gaps), downloads 360p, 
runs Gemini analysis, and updates Supabase.
"""
from __future__ import annotations

import os
import subprocess
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase_utils import query_supabase, upsert_supabase, delete_supabase
from gemini_extractor import process_video_multimodal
from structured_logger import get_logger

_log = get_logger("multimodal_backfill")

def download_video(video_id: str, output_path: str | Path) -> bool:
    """Download 360p video using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    _log.info(f"Downloading {video_id} (360p)...")
    cmd = [
        "yt-dlp",
        "-f", "best[height<=360]",
        "-o", str(output_path),
        url
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        _log.error(f"Failed to download {video_id}: {e.stderr.decode()}")
        return False

def backfill_video(video_id: str, podcast: str):
    """Process a single video through the multimodal pipeline."""
    temp_file = Path(f"temp_{video_id}.mp4")
    
    try:
        if not download_video(video_id, temp_file):
            return
        
        # 1. Run Gemini
        result = process_video_multimodal(temp_file)
        if not result:
            _log.error(f"Gemini returned empty result for {video_id}")
            return
        
        # 2. Update Transcription
        if result.get("transcription"):
            upsert_supabase("transcriptions", {
                "video_id": video_id,
                "raw_text": result["transcription"],
                "language": "en"
            })
            _log.info(f"Updated transcription for {video_id}")
        
        # 3. Update Visual Moments
        if result.get("visual_moments"):
            # Delete old ones first
            delete_supabase("visual_moments", {"video_id": f"eq.{video_id}"})
            
            moments = []
            for m in result["visual_moments"]:
                moments.append({
                    "video_id": video_id,
                    "podcast": podcast,
                    "start_time_sec": m.get("start_time_sec"),
                    "end_time_sec": m.get("end_time_sec"),
                    "description": m.get("description"),
                    "transcript_excerpt": m.get("transcript_excerpt")
                })
            upsert_supabase("visual_moments", moments)
            _log.info(f"Inserted {len(moments)} visual moments for {video_id}")
            
        # 4. Update Insights
        if result.get("insights"):
            # Delete old ones first
            delete_supabase("insights", {"video_id": f"eq.{video_id}"})
            
            insights = []
            for i in result["insights"]:
                insights.append({
                    "video_id": video_id,
                    "podcast": podcast,
                    "category": i.get("category", "Tactical Recommendation"),
                    "title": i.get("title"),
                    "description": i.get("description"),
                    "start_time_sec": i.get("start_time_sec"),
                    "end_time_sec": i.get("end_time_sec")
                })
            upsert_supabase("insights", insights)
            _log.info(f"Inserted {len(insights)} insights for {video_id}")
            
    finally:
        if temp_file.exists():
            temp_file.unlink()

def run_backfill(limit: int = 5, only_gaps: bool = True):
    """Main loop for backfill."""
    load_dotenv()
    
    if only_gaps:
        # Find videos with no insights
        # This is a bit tricky via REST if we can't join. 
        # I'll fetch all videos and all video_ids in insights and diff.
        all_videos = query_supabase("videos", select="video_id,podcast")
        existing_insight_ids = set(v["video_id"] for v in query_supabase("insights", select="video_id"))
        
        targets = [v for v in all_videos if v["video_id"] not in existing_insight_ids]
        _log.info(f"Found {len(targets)} videos with zero insights.")
    else:
        targets = query_supabase("videos", select="video_id,podcast", params={"limit": limit})
        _log.info(f"Processing top {len(targets)} videos.")

    for i, target in enumerate(targets[:limit]):
        vid = target["video_id"]
        pod = target["podcast"]
        _log.info(f"[{i+1}/{limit}] Processing {vid} ({pod})...")
        try:
            backfill_video(vid, pod)
        except Exception as e:
            _log.error(f"FAILED to process video {vid}: {e}")
            continue

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--all", action="store_true", help="Process all videos, not just gaps")
    args = parser.parse_args()
    
    run_backfill(limit=args.limit, only_gaps=not args.all)
