"""
Reset processed flag for newsletters with zero insights to trigger backfill.
"""
import os
import requests
from dotenv import load_dotenv
from supabase_utils import query_supabase

load_dotenv()

URL = os.environ.get("SUPABASE_URL") + "/rest/v1"
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

def reset_silent_failures():
    # 1. Get all newsletters marked processed
    processed_newsletters = query_supabase("newsletters", {"processed": "eq.true"}, "id")
    processed_ids = set(n["id"] for n in processed_newsletters)
    
    # 2. Get all newsletter_ids that HAVE insights
    insight_ids = set(v["newsletter_id"] for v in query_supabase("newsletter_insights", select="newsletter_id"))
    
    # 3. Silent failures = processed but NO insights
    silent_failures = [nid for nid in processed_ids if nid not in insight_ids]
    
    print(f"Found {len(silent_failures)} silent failures (processed=True but 0 insights).")
    
    if not silent_failures:
        return
    
    # 4. Reset them to processed=false
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    # We can do this in batches or one by one if the list is small. 
    # For ~200, we can use a filter or loop.
    count = 0
    for nid in silent_failures:
        url = f"{URL}/newsletters?id=eq.{nid}"
        response = requests.patch(url, headers=headers, json={"processed": False})
        if response.status_code == 204:
            count += 1
            
    print(f"Successfully reset {count} newsletters to processed=False.")

if __name__ == "__main__":
    reset_silent_failures()
