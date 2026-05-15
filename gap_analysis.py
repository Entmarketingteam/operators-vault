
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")

def run_query(query, title):
    print(f"\n--- {title} ---")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        cur.execute(query)
        colnames = [desc[0] for desc in cur.description]
        print("\t".join(colnames))
        rows = cur.fetchall()
        for row in rows:
            print("\t".join(str(x) for x in row))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

# Gap 1: Newsletters with zero insights
run_query("""
SELECT source, processed, last_error is not null as has_error, COUNT(*) 
FROM newsletters 
WHERE id NOT IN (SELECT newsletter_id FROM newsletter_insights) 
GROUP BY source, processed, last_error is not null
ORDER BY source, processed;
""", "Newsletters with Zero Insights")

# Gap 1b: Newsletters with errors
run_query("""
SELECT source, last_error, COUNT(*)
FROM newsletters
WHERE last_error IS NOT NULL
GROUP BY source, last_error;
""", "Newsletter Errors")

# Gap 2: Videos with zero insights
run_query("""
SELECT v.podcast, COUNT(v.video_id) as zero_insight_videos,
       COUNT(t.id) as has_transcription,
       COUNT(v.video_id) - COUNT(t.id) as missing_transcription
FROM videos v
LEFT JOIN transcriptions t ON t.video_id = v.video_id
WHERE v.video_id NOT IN (SELECT video_id FROM insights)
GROUP BY v.podcast;
""", "Videos with Zero Insights")

# Gap 3: Taylor Holiday Sampling
run_query("""
SELECT id, subject, length(body_text) as body_len, left(body_text, 100) as body_sample
FROM newsletters
WHERE source = 'taylor_holiday'
LIMIT 5;
""", "Taylor Holiday Sampling")

# Gap 4: Podcast Yield
run_query("""
SELECT podcast, COUNT(*) as total_insights, 
       (SELECT COUNT(*) FROM videos WHERE podcast = v.podcast) as video_count,
       (CAST(COUNT(*) AS FLOAT) / NULLIF((SELECT COUNT(*) FROM videos WHERE podcast = v.podcast), 0)) as insight_yield
FROM insights v
GROUP BY podcast;
""", "Insight Yield per Podcast")
