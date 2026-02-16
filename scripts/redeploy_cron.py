"""
Redeploy the vault-sync-cron service. Use this to stop a stuck cron run:
Railway has no "stop" for a running execution; redeploying the cron service
terminates the current run and starts fresh.
"""
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

CRON_SERVICE_ID = "21ebfe00-499d-4865-afef-37a0ebce317c"  # vault-sync-cron (recreated)
ENVIRONMENT_ID = os.environ.get("RAILWAY_ENVIRONMENT_ID", "e0fcc82f-5265-4be0-a27e-cae3acdd6a3f")
token = os.environ.get("RAILWAY_API_TOKEN", "").strip()

if not token:
    print("RAILWAY_API_TOKEN required (e.g. from Doppler or .env)", file=sys.stderr)
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
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
            "serviceId": CRON_SERVICE_ID,
            "environmentId": ENVIRONMENT_ID,
        },
    },
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    timeout=30,
)

if r.status_code != 200:
    print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
    sys.exit(1)

data = r.json()
if data.get("errors"):
    print(f"Error: {data['errors']}", file=sys.stderr)
    sys.exit(1)

if data.get("data", {}).get("serviceInstanceDeploy"):
    print("Cron service redeploy triggered.")
    print("This should stop the stuck run and start a fresh deployment.")
    print("Check Railway Dashboard -> vault-sync-cron -> Deployments")
else:
    print(f"Unexpected response: {data}", file=sys.stderr)
    sys.exit(1)
