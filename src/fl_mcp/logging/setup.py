"""Structured logging helpers used by CLI and server startup paths."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Small JSON formatter for startup/runtime logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a single-line JSON string."""
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in ("message", "args"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.exc_text:
            payload["exc_text"] = record.exc_text
        return json.dumps(payload, default=str)


def configure_logging(level: str | int = "INFO") -> None:
    """Configure root logger with JSON output for consistent transport logs."""
    if isinstance(level, str):
        resolved_level = getattr(logging, level.upper(), logging.INFO)
    else:
        resolved_level = level

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(resolved_level)
    root.addHandler(handler)
