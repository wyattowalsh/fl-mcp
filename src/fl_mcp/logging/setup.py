"""Loguru setup helpers."""

import json
import sys
from typing import Any

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging and local console output."""
    logger.remove()
    logger.add(sys.stderr, level=level, format="<green>{time}</green> | <level>{level}</level> | {message}")


def log_json(event: str, **payload: Any) -> None:
    """Emit a structured JSON log event."""
    logger.info(json.dumps({"event": event, **payload}, sort_keys=True))
