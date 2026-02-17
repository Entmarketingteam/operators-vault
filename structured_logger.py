"""
Structured JSON logging for Operators Vault.

Provides one-object-per-line JSON logs with correct log levels,
job lifecycle tracking, and Railway-compatible output.

Usage:
    from structured_logger import get_logger, log_job_event
    logger = get_logger(__name__)
    logger.info("message", extra={"video_id": "abc123"})
    log_job_event("job-123", "started", {"type": "sync"})
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge extra fields (skip standard LogRecord attributes)
        _skip = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "pathname",
            "filename", "module", "levelno", "levelname", "msecs",
            "processName", "process", "threadName", "thread", "taskName",
            "message",
        }
        for k, v in record.__dict__.items():
            if k not in _skip and not k.startswith("_"):
                entry[k] = v
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def _setup_root_logger() -> None:
    """Configure root logger with JSON formatter, once."""
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JSONFormatter)
           for h in root.handlers):
        return  # already configured

    # Remove existing handlers to prevent duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))


# Auto-configure on import
_setup_root_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger that outputs structured JSON."""
    return logging.getLogger(name)


def log_job_event(
    job_id: str,
    event: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Log a job lifecycle event with structured data.

    Events: started, progress, heartbeat, completed, failed, cancelled
    """
    logger = get_logger("jobs")
    data: dict[str, Any] = {"job_id": job_id, "event": event}
    if extra:
        data.update(extra)

    level = logging.INFO
    if event == "failed":
        level = logging.ERROR
    elif event == "heartbeat":
        level = logging.DEBUG

    logger.log(level, f"job {event}", extra=data)
