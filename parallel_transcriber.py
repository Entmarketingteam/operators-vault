import os
import sys
import json
import time
import subprocess
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Define directories
OP_VAULT_DIR = Path("/Users/ethanatchley/Desktop/operators-vault")
_env_path = OP_VAULT_DIR / ".env"
load_dotenv(_env_path)

API_KEY = os.environ.get("DEEPGRAM_API_KEY")
if not API_KEY:
    print("FATAL: DEEPGRAM_API_KEY not found in operators-vault .env file.")
    sys.exit(1)

OUTPUT_DIR = Path("/Users/ethanatchley/Desktop/Jeremy_Haynes_Scale")
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"
RAW_JSON_DIR = OUTPUT_DIR / "raw_json"

TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)

# Define list of videos with IDs and Titles
VIDEOS = [
    # Playlist (Selling to the Rich / Strategy)
    {"id": "yjXH65RtOII", "title": "How To ACTUALLY Sell To Rich People (Step-By-Step)", "type": "playlist"},
    {"id": "h-XgFro-z78", "title": "The BEST Way To Advertise to Rich People (2025+)", "type": "playlist"},
    {"id": "jPCdfQczBgc", "title": "How To Create Offers Rich People ACTUALLY Buy (ULTIMATE GUIDE)", "type": "playlist"},
    {"id": "j8RV1aQqewk", "title": "How To Create A $1M_Month Video Sales Letter (VSL)", "type": "playlist"},
    {"id": "Sg6wEe0IzVc", "title": "How To Build Call Funnels That Make Rich People Buy (The Right Way)", "type": "playlist"},
    {"id": "h5hglsEeDM0", "title": "Selling To The Rich Vs The Public - Everything You MUST Know", "type": "playlist"},
    # Jeremy Haynes Channel (Live Scaling / Tear-downs)
    {"id": "ipMCyWJMpNk", "title": "Helping This $2M_Mo Business Owner Tack On The Next $1M_Mo", "type": "channel"},
    {"id": "OOc6FcMD_cA", "title": "Helping This $1.3M_Mo Marketing Agency Owner Scale In 79 Mins", "type": "channel"},
    {"id": "QTOHLhShL9c", "title": "Watch Me LIVE Scale This $250K_Mo Marketing Agency In 59 Mins", "type": "channel"},
    {"id": "OD_FuPrEn5w", "title": "Watch Me LIVE Fix This $460K_Mo Coaching Business In 91 Mins", "type": "channel"},
    {"id": "a9qeY_A89X8", "title": "Watch Me LIVE Scale This $508K_Month Info Business In 77 Mins", "type": "channel"},
    {"id": "sQ2diSyCd1w", "title": "Watch Me LIVE Fix This $114K_Mo Content Agency In 75 Mins", "type": "channel"},
    {"id": "0XtjQc5Madg", "title": "Watch Me LIVE Scale This $550K_Mo Trading Offer In 68 Mins", "type": "channel"},
    {"id": "z9x1OJUD8-Q", "title": "Watch Me LIVE Fix This $500K_Mo AI Automation Business In 69 Mins", "type": "channel"},
    {"id": "C7sClO-kLVw", "title": "Watch Me LIVE Scale This $200K_Month Agency Owner In 81 Mins", "type": "channel"},
    {"id": "dP8M1RcAe-c", "title": "I Fixed This $200K+_Mo Coaching Business's Paid Ads Funnel (Live)", "type": "channel"}
]

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

def clean_filename(title):
    for c in r'<>:"/\|?*':
        title = title.replace(c, "_")
    return title.strip()

def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    hours = int(mins // 60)
    if hours > 0:
        mins = mins % 60
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"

def process_video(video, worker_id):
    vid = video["id"]
    raw_title = video["title"]
    clean_t = clean_filename(raw_title)
    video_type = video["type"]
    
    transcript_file = TRANSCRIPTS_DIR / f"{vid}_{clean_t}.md"
    raw_json_file = RAW_JSON_DIR / f"{vid}.json"
    
    # Check if already done
    if transcript_file.exists() and raw_json_file.exists():
        print(f"[{worker_id}] {vid} already transcribed. Skipping.", flush=True)
        return True, vid

    print(f"[{worker_id}] Starting {vid} - {raw_title} ({video_type})", flush=True)
    
    # 1. Download audio via yt-dlp (highly compressed to 32k mono mp3 for speed)
    temp_audio = Path(f"/tmp/transcribe_{vid}.mp3")
    if temp_audio.exists():
        temp_audio.unlink()
        
    print(f"[{worker_id}] [{vid}] Downloading audio stream...", flush=True)
    cmd = [
        "yt-dlp",
        "-f", "ba",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "32k",
        "-o", f"/tmp/transcribe_{vid}.%(ext)s",
        f"https://www.youtube.com/watch?v={vid}"
    ]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        if res.returncode != 0:
            print(f"[{worker_id}] [{vid}] yt-dlp error: {res.stderr[:200]}", flush=True)
            return False, vid
    except Exception as e:
        print(f"[{worker_id}] [{vid}] yt-dlp failed: {e}", flush=True)
        return False, vid

    if not temp_audio.exists():
        print(f"[{worker_id}] [{vid}] Downloaded audio file not found.", flush=True)
        return False, vid

    size_mb = temp_audio.stat().st_size / (1024 * 1024)
    print(f"[{worker_id}] [{vid}] Audio downloaded. Size: {size_mb:.2f} MB. Sending to Deepgram...", flush=True)

    # 2. Transcribe via Deepgram
    from deepgram import DeepgramClient
    
    try:
        client = DeepgramClient(api_key=API_KEY)
        with open(temp_audio, "rb") as f:
            audio_bytes = f.read()
            
        response = client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-2",
            smart_format=True,
            punctuate=True,
            utterances=True,
            diarize=True,
        )
        
        result = response.model_dump()
        
        # Save raw JSON
        with open(raw_json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)
            
    except Exception as e:
        print(f"[{worker_id}] [{vid}] Deepgram error: {e}", flush=True)
        if temp_audio.exists():
            temp_audio.unlink()
        return False, vid

    # 3. Clean up temp audio file
    if temp_audio.exists():
        temp_audio.unlink()

    # 4. Parse and format Deepgram results
    try:
        results = result.get("results") or {}
        channels = results.get("channels") or []
        full_text = ""
        if channels:
            full_text = channels[0].get("alternatives", [{}])[0].get("transcript", "")
            
        utterances = results.get("utterances") or []
        
        # Format transcript as markdown
        md_content = [
            f"# {raw_title}",
            f"- **YouTube URL**: https://www.youtube.com/watch?v={vid}",
            f"- **Video ID**: {vid}",
            f"- **Category**: {video_type.upper()}",
            f"- **Processed At**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"Character count: {len(full_text)} | Segment count: {len(utterances)}",
            "",
            "## Transcript",
            ""
        ]
        
        if utterances:
            for u in utterances:
                start = u.get("start", 0)
                speaker = u.get("speaker", 0)
                text = u.get("transcript", "").strip()
                if text:
                    md_content.append(f"**Speaker {speaker}** ({format_time(start)}): {text}")
                    md_content.append("")
        else:
            md_content.append(full_text)
            
        # Write markdown transcript
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
            
        print(f"[{worker_id}] [{vid}] SUCCESS! Saved transcript.", flush=True)
        return True, vid
        
    except Exception as e:
        print(f"[{worker_id}] [{vid}] Formatting error: {e}", flush=True)
        return False, vid

def main():
    print(f"=== Operators Vault: Parallel Transcriber ===", flush=True)
    print(f"Loaded Deepgram Key: {API_KEY[:4]}...{API_KEY[-4:]}", flush=True)
    print(f"Output Directory: {OUTPUT_DIR}", flush=True)
    print(f"Total videos to process: {len(VIDEOS)}\n", flush=True)
    
    start_time = time.time()
    success_count = 0
    results_dict = {}
    
    # Run with 4 concurrent workers (Thread pool)
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit tasks
        futures = {
            executor.submit(process_video, video, f"Worker-{i%4 + 1}"): video
            for i, video in enumerate(VIDEOS)
        }
        
        for future in as_completed(futures):
            video = futures[future]
            try:
                ok, vid = future.result()
                if ok:
                    success_count += 1
                    results_dict[vid] = "SUCCESS"
                else:
                    results_dict[vid] = "FAILED"
            except Exception as e:
                print(f"Future raised exception for {video['id']}: {e}", flush=True)
                results_dict[video["id"]] = "ERROR"

    elapsed = time.time() - start_time
    print(f"\n=== PROCESS COMPLETE ===", flush=True)
    print(f"Successfully processed: {success_count}/{len(VIDEOS)}", flush=True)
    print(f"Time elapsed: {elapsed:.2f}s", flush=True)
    print(f"Results summary:")
    for vid, status in results_dict.items():
        print(f"- {vid}: {status}", flush=True)

if __name__ == "__main__":
    main()
