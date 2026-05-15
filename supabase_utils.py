import os
import requests
from dotenv import load_dotenv

load_dotenv()

URL = os.environ.get("SUPABASE_URL") + "/rest/v1"
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

def query_supabase(table, params=None, select="*"):
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json"
    }
    url = f"{URL}/{table}"
    query_params = {"select": select}
    if params:
        query_params.update(params)
    
    response = requests.get(url, headers=headers, params=query_params)
    response.raise_for_status()
    return response.json()

def upsert_supabase(table, data):
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{URL}/{table}"
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

def delete_supabase(table, params):
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}"
    }
    url = f"{URL}/{table}"
    response = requests.delete(url, headers=headers, params=params)
    response.raise_for_status()
    return response.status_code

if __name__ == "__main__":
    # Test: Get a video_id from marketing_operator
    videos = query_supabase("videos", {"podcast": "eq.marketing_operator", "limit": 1}, "video_id")
    if videos:
        print(videos[0]["video_id"])
