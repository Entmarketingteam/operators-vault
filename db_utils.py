"""
Shared Supabase/psycopg2 connection helpers.

Why this exists
---------------
The Supabase **transaction pooler on port 6543** has been returning
``OperationalError: SSL connection has been closed unexpectedly`` on every
connection (verified 0/6 success), which took down every API endpoint and the
ingestion pipeline. The **session pooler on port 5432** is healthy, so all
connections are routed there.

Trade-off: the session pooler caps at ~15 concurrent client connections
(verified: 12/12 ok, 15/20 ok). Callers that maintain their own connection pool
must keep ``maxconn`` comfortably below that ceiling (see ``DB_POOL_MAX``).

PR #10 deliberately forced everything onto 6543 ("thousands of connections" in
transaction mode). That was correct for many ephemeral clients, but this app
runs long-lived containers with their own client-side pool — session mode (5432)
is the right fit and is what actually works today.
"""
from __future__ import annotations

import os
import time

# Safe ceiling for the session pooler (5432). Verified empirically: 5432 starts
# refusing connections somewhere between 15 and 20 concurrent. Keep client pools
# below this and leave headroom for raw (non-pooled) connect sites.
DB_POOL_MAX = 10

# psycopg2 OperationalError messages that indicate a dropped/transient pooler
# connection where a fresh connect is worth retrying.
_TRANSIENT_MARKERS = (
    "ssl connection has been closed unexpectedly",
    "server closed the connection unexpectedly",
    "connection already closed",
    "could not connect to server",
    "connection timed out",
)


def resolve_db_url() -> str | None:
    """Return DATABASE_URL with the Supabase pooler routed to the working port.

    The Supabase transaction pooler (6543) is currently dropping SSL on every
    connection; the session pooler (5432) is healthy. Rewrite 6543 -> 5432 for
    Supabase pooler URLs only, leaving non-Supabase / direct URLs untouched.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    if "pooler.supabase.com" in url and ":6543" in url:
        url = url.replace(":6543", ":5432")
    return url


def is_transient_db_error(exc: Exception) -> bool:
    """True if the error looks like a recoverable pooler/connection drop."""
    msg = str(exc).lower()
    return any(m in msg for m in _TRANSIENT_MARKERS)


def connect(url: str | None = None, *, retries: int = 3, **kwargs):
    """psycopg2.connect with retry on transient pooler/SSL drops.

    Opens a *fresh* connection on each attempt (a pooler-closed socket cannot be
    reused) and validates it with ``SELECT 1`` before returning, so callers never
    receive a dead-on-arrival connection. Extra kwargs (connect_timeout, options,
    sslmode, ...) are passed straight through to psycopg2.connect.
    """
    import psycopg2

    if url is None:
        url = resolve_db_url()
    if not url:
        raise ValueError("DATABASE_URL not set")

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(url, **kwargs)
            # Probe so a dead-but-accepted connection fails here (where we can
            # retry) rather than on the caller's first execute.
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            # Roll back the probe's implicit transaction so the connection is
            # returned in a clean (idle) state — INTRANS would break callers that
            # set conn.autocommit and leaks "idle in transaction" backends.
            conn.rollback()
            return conn
        except Exception as e:  # noqa: BLE001 - want broad transient catch
            last_exc = e
            if not is_transient_db_error(e) or attempt == retries - 1:
                raise
            # Exponential backoff: 0.25s, 0.5s, 1s ...
            time.sleep(0.25 * (2 ** attempt))
    assert last_exc is not None
    raise last_exc
