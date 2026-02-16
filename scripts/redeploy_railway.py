"""Trigger a Railway redeploy for the main service."""
import os
import sys
import json
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

# Service ID and Environment ID from railway link
SERVICE_ID = "64aa9bda-8cc2-4a79-acf0-4fd10cca1301"
ENVIRONMENT_ID = "e0fcc82f-5265-4be0-a27e-cae3acdd6a3f"
token = os.environ.get("RAILWAY_API_TOKEN", "").strip()

if not token:
    print("RAILWAY_API_TOKEN not set. Use Doppler or set in .env", file=sys.stderr)
    sys.exit(1)

r = httpx.post(
    "https://backboard.railway.com/graphql/v2",
    json={
        "query": """
        mutation deploy($serviceId: String!, $environmentId: String!) {
          serviceInstanceDeploy(serviceId: $serviceId, environmentId: $environmentId)
        }
        """,
        "variables": {
            "serviceId": SERVICE_ID,
            "environmentId": ENVIRONMENT_ID
        }
    },
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    timeout=30,
)

if r.status_code == 200:
    data = r.json()
    if data.get("errors"):
        print(f"Error: {data['errors']}", file=sys.stderr)
        sys.exit(1)
    success = data.get("data", {}).get("serviceInstanceDeploy")
    if success:
        print("Redeploy triggered successfully!")
        print("Check Railway Dashboard -> superb-smile -> Deployments")
    else:
        print(f"Unexpected response: {data}")
else:
    print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
    sys.exit(1)
