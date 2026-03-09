"""
Newsletter backfill: fetch all historical emails from Gmail → POST to Railway /ingest-newsletter.
Uses existing gws OAuth credentials (~/.config/gws/credentials_entagency.json).

Usage:
  python3 scripts/run_newsletter_backfill.py
  python3 scripts/run_newsletter_backfill.py --source nik_sharma   # single source
  python3 scripts/run_newsletter_backfill.py --dry-run             # print counts only
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ── Config ────────────────────────────────────────────────────────────────────

RAILWAY_URL = "https://superb-smile-production.up.railway.app"
CREDS_PATH = Path.home() / ".config/gws/credentials.json"  # main gws credentials (has gmail.modify scope)
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

SOURCES = [
    {
        "source": "nik_sharma",
        "author": "Nik Sharma",
        "query": "from:niksharma@workweek.com",
    },
    {
        "source": "taylor_holiday",
        "author": "Taylor Holiday / CTC",
        "query": "from:taylorholiday@commonthreadco.com",
    },
    {
        "source": "matt_bertulli",
        "author": "Matt Bertulli",
        "query": "from:m@mattbertulli.com",
    },
    {
        "source": "chase_dimond",
        "author": "Chase Dimond",
        "query": "from:chase@chasedimond.com OR from:ecomemailmarketer@mail.beehiiv.com",
    },
    {
        "source": "operators_newsletter",
        "author": "Operators Newsletter",
        "query": "from:news@operatorscontent.com",
    },
]

# ── Gmail OAuth ───────────────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    raw = json.loads(CREDS_PATH.read_text())
    # Don't pass scopes — use token as-is (authorized_user type has no scope restriction on refresh)
    creds = Credentials(
        token=None,  # will be refreshed
        refresh_token=raw["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=raw["client_id"],
        client_secret=raw["client_secret"],
    )
    creds.refresh(Request())
    return creds


def gmail_get(creds: Credentials, path: str, params: dict = {}) -> dict:
    headers = {"Authorization": f"Bearer {creds.token}"}
    r = requests.get(f"{GMAIL_API}/{path}", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Email parsing ──────────────────────────────────────────────────────────────

def decode_b64(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")


def extract_body(payload: dict) -> tuple[str, str]:
    """Return (html_body, text_body) from Gmail message payload."""
    html_body = ""
    text_body = ""

    def walk(part: dict):
        nonlocal html_body, text_body
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if data:
            decoded = decode_b64(data)
            if mime == "text/html" and not html_body:
                html_body = decoded
            elif mime == "text/plain" and not text_body:
                text_body = decoded
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return html_body, text_body


def extract_header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ── Fetch all message IDs for a query ─────────────────────────────────────────

def fetch_message_ids(creds: Credentials, query: str) -> list[str]:
    ids = []
    page_token = None
    while True:
        params: dict = {"q": query, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        data = gmail_get(creds, "messages", params)
        for m in data.get("messages", []):
            ids.append(m["id"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids


# ── POST to Railway ────────────────────────────────────────────────────────────

def post_to_railway(payload: dict, dry_run: bool) -> dict:
    if dry_run:
        return {"status": "dry_run", "email_id": payload["email_id"]}
    try:
        r = requests.post(
            f"{RAILWAY_URL}/ingest-newsletter",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"status": "error", "error": str(e), "email_id": payload.get("email_id", "")}


# ── Main ───────────────────────────────────────────────────────────────────────

def run_source(creds: Credentials, source_cfg: dict, dry_run: bool, skip_existing: set):
    source = source_cfg["source"]
    author = source_cfg["author"]
    query = source_cfg["query"]

    print(f"\n[{source}] Fetching message IDs...")
    ids = fetch_message_ids(creds, query)
    print(f"[{source}] Found {len(ids)} emails")

    new_ids = [i for i in ids if i not in skip_existing]
    print(f"[{source}] {len(new_ids)} new (not yet ingested)")

    stats = {"processed": 0, "duplicate": 0, "skipped": 0, "error": 0}

    for i, msg_id in enumerate(new_ids, 1):
        # Refresh token if needed
        if not creds.valid:
            creds.refresh(Request())

        try:
            msg = gmail_get(creds, f"messages/{msg_id}", {"format": "full"})
        except Exception as e:
            print(f"  [{i}/{len(new_ids)}] ERROR fetching {msg_id}: {e}")
            stats["error"] += 1
            continue

        payload_data = msg.get("payload", {})
        html_body, text_body = extract_body(payload_data)
        subject = extract_header(payload_data, "subject")
        date_str = extract_header(payload_data, "date")
        sender = extract_header(payload_data, "from")

        # Parse date to ISO
        published_at = None
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                published_at = parsedate_to_datetime(date_str).isoformat()
            except Exception:
                pass

        payload = {
            "email_id": msg_id,
            "source": source,
            "author": author,
            "subject": subject,
            "published_at": published_at,
            "sender_email": sender,
            "body_html": html_body,
            "body_text": text_body,
        }

        result = post_to_railway(payload, dry_run)
        status = result.get("status", "unknown")
        insights = result.get("insights_count", 0)

        if status == "processed":
            stats["processed"] += 1
            print(f"  [{i}/{len(new_ids)}] OK — {subject[:60]} — {insights} insights")
        elif status == "duplicate":
            stats["duplicate"] += 1
        elif status == "skipped":
            stats["skipped"] += 1
            print(f"  [{i}/{len(new_ids)}] SKIP — {result.get('reason', '')} — {subject[:50]}")
        elif status == "dry_run":
            stats["processed"] += 1
            print(f"  [{i}/{len(new_ids)}] DRY RUN — {subject[:60]}")
        else:
            stats["error"] += 1
            print(f"  [{i}/{len(new_ids)}] ERROR — {result.get('error', status)} — {subject[:50]}")

        # Brief pause to avoid overwhelming Railway
        time.sleep(0.5)

    print(f"[{source}] Done: {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Only run this source slug")
    parser.add_argument("--dry-run", action="store_true", help="Fetch IDs only, don't POST")
    args = parser.parse_args()

    print("Authenticating with Gmail...")
    creds = get_credentials()
    print("Auth OK")

    # Check Railway health
    if not args.dry_run:
        try:
            r = requests.get(f"{RAILWAY_URL}/health", timeout=10)
            print(f"Railway health: {r.json().get('status')}")
        except Exception as e:
            print(f"WARNING: Railway check failed: {e}")

    sources = [s for s in SOURCES if not args.source or s["source"] == args.source]
    if not sources:
        print(f"No sources matched '{args.source}'")
        sys.exit(1)

    totals = {"processed": 0, "duplicate": 0, "skipped": 0, "error": 0}
    for source_cfg in sources:
        stats = run_source(creds, source_cfg, dry_run=args.dry_run, skip_existing=set())
        for k in totals:
            totals[k] += stats.get(k, 0)

    print(f"\n=== BACKFILL COMPLETE ===")
    print(f"Total: {totals}")


if __name__ == "__main__":
    main()
