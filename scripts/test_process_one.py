"""Test processing one video to see the actual error."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
    sys.exit(1)

# Get first unprocessed video
api_url = "https://superb-smile-production.up.railway.app"
print("Getting stats to find a video ID...")
r = httpx.get(f"{api_url}/stats", timeout=15, verify=False)
if r.status_code != 200:
    print(f"Failed to get stats: {r.status_code}", file=sys.stderr)
    sys.exit(1)

data = r.json()
podcasts = data.get("by_podcast", {})
if not podcasts:
    print("No videos found in stats", file=sys.stderr)
    sys.exit(1)

# Get episodes to find a video ID
print("Getting episodes...")
r2 = httpx.get(f"{api_url}/episodes?limit=1", timeout=15, verify=False)
if r2.status_code != 200:
    print(f"Failed to get episodes: {r2.status_code}", file=sys.stderr)
    sys.exit(1)

episodes_data = r2.json()
episodes = episodes_data.get("episodes", [])
if not episodes:
    print("No episodes found. Trying to process via API directly...")
    # Try to trigger process-new and check logs
    print("\nTriggering process-new/async to see errors in Railway logs...")
    r3 = httpx.post(f"{api_url}/process-new/async", timeout=15, verify=False)
    if r3.status_code == 202:
        job = r3.json()
        job_id = job.get("job_id")
        print(f"Job started: {job_id}")
        print(f"\nCheck Railway logs for errors:")
        print(f"  Railway Dashboard -> superb-smile -> Logs")
        print(f"\nOr check job status:")
        print(f"  GET {api_url}/jobs/{job_id}")
    else:
        print(f"Failed to trigger: {r3.status_code} {r3.text}")
    sys.exit(0)

video = episodes[0]
video_id = video.get("video_id")
podcast = video.get("podcast", "9operators")

print(f"\nTesting processing for video: {video_id} ({podcast})")
print(f"Calling POST {api_url}/process")
print(f"Body: {{'video_id': '{video_id}', 'podcast': '{podcast}'}}")

r4 = httpx.post(
    f"{api_url}/process",
    json={"video_id": video_id, "podcast": podcast},
    timeout=300,  # 5 min timeout
    verify=False
)

if r4.status_code == 200:
    result = r4.json()
    print(f"\n[SUCCESS] Processing completed!")
    print(f"Result: {result}")
elif r4.status_code == 500:
    error = r4.json() if r4.headers.get("content-type", "").startswith("application/json") else r4.text
    print(f"\n[ERROR] Processing failed:")
    print(f"Status: {r4.status_code}")
    print(f"Error: {error}")
    print(f"\nCheck Railway logs for detailed error messages:")
    print(f"  Railway Dashboard -> superb-smile -> Logs")
else:
    print(f"\n[ERROR] Unexpected status: {r4.status_code}")
    print(f"Response: {r4.text}")
