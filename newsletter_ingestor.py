"""
Newsletter ingestion pipeline for Operators Vault.
Accepts email content (from n8n or direct call), strips HTML, extracts insights via Claude,
stores in Supabase newsletters + newsletter_insights tables.

Sources: nik_sharma | taylor_holiday | matt_bertulli | chase_dimond | operators_newsletter
"""
from __future__ import annotations

import html
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

# ── Source config ─────────────────────────────────────────────────────────────

# Hardcoded fallback — used if DB is unavailable or table doesn't exist yet
_NEWSLETTER_SOURCES_FALLBACK = {
    "nik_sharma": {
        "author": "Nik Sharma",
        "label_id": "Label_422580267025539773",
        "senders": ["niksharma@workweek.com"],
    },
    "taylor_holiday": {
        "author": "Taylor Holiday / CTC",
        "label_id": "Label_527847910175146065",
        "senders": ["taylorholiday@commonthreadco.com"],
    },
    "matt_bertulli": {
        "author": "Matt Bertulli",
        "label_id": "Label_529153241593133290",
        "senders": ["m@mattbertulli.com"],
    },
    "chase_dimond": {
        "author": "Chase Dimond",
        "senders": ["chase@chasedimond.com", "ecomemailmarketer@mail.beehiiv.com"],
    },
    "operators_newsletter": {
        "author": "Operators Newsletter",
        "label_id": "Label_4710583513291043383",
        "senders": ["news@operatorscontent.com"],
    },
}


def load_newsletter_sources_from_db() -> dict:
    """
    Load newsletter sources from newsletter_source_configs table.
    Returns a dict keyed by slug with {author, gmail_query, senders} shape.
    Falls back to _NEWSLETTER_SOURCES_FALLBACK on any error.
    """
    try:
        import psycopg2
        url = os.environ.get("DATABASE_URL", "")
        if not url:
            return _NEWSLETTER_SOURCES_FALLBACK
        conn = psycopg2.connect(url, sslmode="require")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, author, gmail_query FROM newsletter_source_configs WHERE active = TRUE ORDER BY created_at"
            )
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return _NEWSLETTER_SOURCES_FALLBACK
        result = {}
        for slug, author, gmail_query in rows:
            # Parse senders from gmail_query (extract email addresses)
            senders = re.findall(r"from:(\S+@\S+\.\S+)", gmail_query)
            result[slug] = {
                "author": author,
                "gmail_query": gmail_query,
                "senders": senders,
            }
        return result
    except Exception:
        return _NEWSLETTER_SOURCES_FALLBACK


# Load from DB at module import time; falls back to hardcoded if DB unavailable
NEWSLETTER_SOURCES = load_newsletter_sources_from_db()

# Infer source from sender email
_SENDER_TO_SOURCE: dict[str, str] = {}
for _slug, _cfg in NEWSLETTER_SOURCES.items():
    for _sender in _cfg.get("senders", []):
        _SENDER_TO_SOURCE[_sender.lower()] = _slug


def infer_source_from_sender(sender_email: str) -> str | None:
    """Given a raw From header like 'Nik Sharma <niksharma@workweek.com>', return source slug."""
    m = re.search(r"<([^>]+)>", sender_email)
    addr = (m.group(1) if m else sender_email).strip().lower()
    return _SENDER_TO_SOURCE.get(addr)


# ── HTML stripping ─────────────────────────────────────────────────────────────

def strip_html(raw: str) -> str:
    """Strip HTML tags, decode entities, collapse whitespace."""
    # Remove style/script blocks
    raw = re.sub(r"<(style|script)[^>]*>[\s\S]*?</\1>", "", raw, flags=re.IGNORECASE)
    # Replace block-level tags with newlines
    raw = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", raw, flags=re.IGNORECASE)
    # Remove remaining tags
    raw = re.sub(r"<[^>]+>", "", raw)
    # Decode HTML entities
    raw = html.unescape(raw)
    # Collapse excessive whitespace / blank lines
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def clean_email_text(text: str) -> str:
    """Remove common newsletter boilerplate: unsubscribe footers, tracking pixels etc."""
    # Stop at common footer markers
    for marker in [
        "unsubscribe", "manage your preferences", "you received this",
        "to stop receiving", "view in browser", "update your preferences",
        "©", "all rights reserved",
    ]:
        idx = text.lower().rfind(marker)
        if idx > len(text) * 0.6:  # only trim if in the last 40%
            text = text[:idx]
    return text.strip()


# ── Text chunking ──────────────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 6000, overlap: int = 300) -> list[str]:
    """Split long text into overlapping chunks for insight extraction."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Try to break at a paragraph boundary
            boundary = text.rfind("\n\n", start, end)
            if boundary > start + max_chars // 2:
                end = boundary
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ── Insight extraction (reuses insight_extractor logic) ───────────────────────

def extract_newsletter_insights(text: str) -> list[dict[str, str]]:
    """Run Claude extraction on newsletter text. Returns list of {category, title, description}."""
    from insight_extractor import _anthropic_message, _load_prompt, parse_extract_insights_output
    tpl = _load_prompt("extract_insights_system", prompt_set="newsletters")
    if not tpl:
        return []
    user = tpl.replace("{transcript}", text)
    system = "You are an expert DTC and eCommerce operator analyst. Follow the instructions exactly."
    raw = _anthropic_message(system, user, model="claude-haiku-4-5-20251001")
    return parse_extract_insights_output(raw)


# ── Supabase storage ───────────────────────────────────────────────────────────

_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                import psycopg2.pool
                url = os.environ.get("DATABASE_URL", "")
                _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, url, sslmode="require")
    return _pool


def _db_conn():
    """Return a connection from the pool (caller must call pool.putconn when done)."""
    import psycopg2
    url = os.environ.get("DATABASE_URL", "")
    return psycopg2.connect(url, sslmode="require")


def upsert_newsletter(
    email_id: str,
    source: str,
    author: str,
    subject: str,
    published_at: str | None,
    body_text: str,
) -> tuple[str, bool]:
    """
    Insert newsletter row. Returns (newsletter_id, is_new).
    Skips if already processed.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            # Check existing
            cur.execute("SELECT id, processed, length(body_text) FROM newsletters WHERE email_id = %s", (email_id,))
            row = cur.fetchone()
            if row:
                existing_id, existing_processed, existing_body_len = str(row[0]), row[1], (row[2] or 0)
                # If we have a substantially longer body, update and reset processed flag
                if not existing_processed and len(body_text) > existing_body_len * 2 and len(body_text) > 500:
                    cur.execute(
                        "UPDATE newsletters SET body_text = %s, processed = FALSE WHERE id = %s",
                        (body_text, existing_id),
                    )
                    conn.commit()
                    return existing_id, True  # treat as new so extraction runs
                return existing_id, False  # already exists, no update needed

            nl_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO newsletters (id, email_id, source, author, subject, published_at, body_text, processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                ON CONFLICT (email_id) DO NOTHING
                """,
                (nl_id, email_id, source, author, subject, published_at, body_text),
            )
            conn.commit()
            return nl_id, True
    finally:
        pool.putconn(conn)


def store_newsletter_insights(newsletter_id: str, source: str, insights: list[dict]) -> int:
    """Insert extracted insights and mark newsletter processed. Returns count inserted."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            for ins in insights:
                cur.execute(
                    """
                    INSERT INTO newsletter_insights (newsletter_id, source, category, title, description, source_chunk)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        newsletter_id,
                        source,
                        ins.get("category", ""),
                        ins.get("title", ""),
                        ins.get("description", ""),
                        ins.get("source_chunk", ""),
                    ),
                )
            # Always mark processed=TRUE, even if no insights (prevents infinite requeue loop)
            cur.execute("UPDATE newsletters SET processed = TRUE WHERE id = %s", (newsletter_id,))
            conn.commit()
        return len(insights)
    finally:
        pool.putconn(conn)


# ── Main entry point ───────────────────────────────────────────────────────────

def ingest_email(
    email_id: str,
    source: str,
    author: str,
    subject: str,
    published_at: str | None,
    body_html: str = "",
    body_text: str = "",
) -> dict[str, Any]:
    """
    Full pipeline: clean text → extract insights → store.
    Returns {"email_id", "newsletter_id", "is_new", "insights_count", "status"}.
    """
    # Clean body
    if body_html and not body_text:
        body_text = strip_html(body_html)
    body_text = clean_email_text(body_text)

    if not body_text or len(body_text) < 100:
        return {"email_id": email_id, "status": "skipped", "reason": "body too short", "insights_count": 0}

    # Upsert newsletter record
    newsletter_id, is_new = upsert_newsletter(email_id, source, author, subject, published_at, body_text)
    if not is_new:
        return {"email_id": email_id, "newsletter_id": newsletter_id, "is_new": False, "status": "duplicate", "insights_count": 0}

    # Extract insights from all chunks
    all_insights: list[dict] = []
    chunks = chunk_text(body_text)
    for chunk in chunks:
        chunk_insights = extract_newsletter_insights(chunk)
        for ins in chunk_insights:
            ins["source_chunk"] = chunk[:500]
        all_insights.extend(chunk_insights)

    # Store
    count = store_newsletter_insights(newsletter_id, source, all_insights)

    return {
        "email_id": email_id,
        "newsletter_id": newsletter_id,
        "is_new": True,
        "status": "processed",
        "insights_count": count,
        "chunks_processed": len(chunks),
    }
