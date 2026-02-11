"""
Push Google OAuth (and enable Email) into Supabase Auth via Management API.
Reads GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from .env and PATCHes the project auth config.
Requires: SUPABASE_MANAGEMENT_TOKEN (create at https://supabase.com/dashboard/account/tokens).
Project ref is read from SUPABASE_URL or default wbdwnlzbgugewtmvahwg.
Run: python scripts/enable_supabase_auth.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

PROJECT_REF = "wbdwnlzbgugewtmvahwg"
API_BASE = "https://api.supabase.com/v1"


def main() -> int:
    # Accept either name (Doppler may have it as supabase_api_key2)
    token = (
        os.environ.get("SUPABASE_MANAGEMENT_TOKEN") or os.environ.get("SUPABASE_API_KEY2") or ""
    ).strip()
    if not token:
        print(
            "SUPABASE_MANAGEMENT_TOKEN or SUPABASE_API_KEY2 required. Create at https://supabase.com/dashboard/account/tokens",
            file=sys.stderr,
        )
        return 1

    url = os.environ.get("SUPABASE_URL", "")
    if url:
        m = re.search(r"https://([a-z0-9]+)\.supabase\.co", url)
        if m:
            global PROJECT_REF
            PROJECT_REF = m.group(1)

    try:
        import httpx
    except ImportError:
        print("pip install httpx", file=sys.stderr)
        return 1

    # Build PATCH body: enable email; enable Google if credentials provided
    body: dict = {"external_email_enabled": True}
    gid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    gsecret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if gid and gsecret:
        body["external_google_enabled"] = True
        body["external_google_client_id"] = gid
        body["external_google_secret"] = gsecret

    r = httpx.patch(
        f"{API_BASE}/projects/{PROJECT_REF}/config/auth",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        print(f"Management API error: {r.status_code} {r.text}", file=sys.stderr)
        return 1
    print("Auth config updated: Email enabled" + ("; Google enabled." if body.get("external_google_enabled") else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
