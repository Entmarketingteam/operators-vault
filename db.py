"""
Central Postgres connection helper for Operators Vault.

Every connection to Supabase MUST go through `db.connect()` so that:
- `statement_timeout` is always overridden (Supabase's transaction pooler
  defaults to a short timeout that silently kills inserts/selects).
- TCP keepalives are always on (detects sockets killed by the pooler's
  idle timeout; without this, stale connections hang or hit opaque errors
  on the next query after a long idle period).
- `connect_timeout` is always bounded (never block a request thread forever
  on a network partition).

History: the newsletter sync (n8n workflow FPWjPuFq2jkPkJmj) silently
failed for a week because `newsletter_ingestor.py` used a long-lived
ThreadedConnectionPool with no statement_timeout or keepalives. The YouTube
pipeline had the fix (commit bc1f21d) but it never propagated. Centralising
here so a single fix benefits every caller.

Enforced by scripts/check_db_connections.py in CI — direct
`psycopg2.connect(...)` calls outside this module must not increase.
"""
from __future__ import annotations

import os
from typing import Any


# Safe defaults applied to every connection.
# Override per-call by passing kwargs to connect() — anything passed wins.
_DEFAULTS: dict[str, Any] = {
    "sslmode": "require",
    # 60s is generous for OLTP-style endpoints. Batch jobs that need longer
    # (e.g. pipeline.py processing a 90-minute transcript) can pass
    # statement_timeout_ms=600000 to bump it.
    "connect_timeout": 15,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

_DEFAULT_STATEMENT_TIMEOUT_MS = 60_000


def connect(
    url: str | None = None,
    *,
    statement_timeout_ms: int = _DEFAULT_STATEMENT_TIMEOUT_MS,
    **overrides: Any,
):
    """
    Return a psycopg2 connection with safe Supabase defaults applied.

    Args:
        url: Postgres DSN. Defaults to $DATABASE_URL.
        statement_timeout_ms: session-level statement_timeout override.
            Defaults to 60s. Batch jobs may pass e.g. 600_000 for 10min.
        **overrides: forwarded to psycopg2.connect; override any default.

    Raises:
        RuntimeError if no URL was given and DATABASE_URL is unset.
    """
    import psycopg2

    dsn = url or os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set and no url was passed")

    kwargs: dict[str, Any] = dict(_DEFAULTS)
    # options= is a libpq string — callers can override by passing options=
    kwargs["options"] = f"-c statement_timeout={int(statement_timeout_ms)}"
    kwargs.update(overrides)

    return psycopg2.connect(dsn, **kwargs)
