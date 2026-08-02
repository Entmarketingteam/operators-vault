import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

ROOT = Path(__file__).resolve().parent
_env = ROOT / ".env"
load_dotenv(_env)

import db_utils

video_ids = [
    # Playlist
    "yjXH65RtOII", "h-XgFro-z78", "jPCdfQczBgc", "j8RV1aQqewk", "Sg6wEe0IzVc", "h5hglsEeDM0",
    # Channel
    "ipMCyWJMpNk", "OOc6FcMD_cA", "QTOHLhShL9c", "OD_FuPrEn5w", "a9qeY_A89X8", "sQ2diSyCd1w",
    "0XtjQc5Madg", "z9x1OJUD8-Q", "C7sClO-kLVw", "dP8M1RcAe-c"
]

db_url = db_utils.resolve_db_url()
if not db_url:
    print("No database URL found")
    exit(1)

conn = db_utils.connect(db_url)
with conn.cursor() as cur:
    # Query for existing transcriptions
    cur.execute(
        "SELECT video_id FROM transcriptions WHERE video_id = ANY(%s)",
        (video_ids,)
    )
    transcribed = {r[0] for r in cur.fetchall()}

    # Query for video titles
    cur.execute(
        "SELECT video_id, title FROM videos WHERE video_id = ANY(%s)",
        (video_ids,)
    )
    video_titles = {r[0]: r[1] for r in cur.fetchall()}

print("TRANSCRIBED VIDEOS IN DB:")
for vid in video_ids:
    status = "✅ YES" if vid in transcribed else "❌ NO"
    title = video_titles.get(vid, "Unknown Title")
    print(f"- {vid}: {status} | {title}")

conn.close()
