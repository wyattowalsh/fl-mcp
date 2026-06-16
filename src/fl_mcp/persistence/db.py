"""Persistence engine setup."""

from __future__ import annotations

import threading

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

from fl_mcp.config.settings import settings

_ENGINE_LOCK = threading.Lock()
_ENGINE: Engine | None = None


def get_engine() -> Engine:
    """Return (and lazily create) the shared SQLAlchemy engine singleton."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = create_engine(settings.database_url, echo=False)
        return _ENGINE


def init_db() -> None:
    """Initialize local SQLite tables."""
    SQLModel.metadata.create_all(get_engine())
