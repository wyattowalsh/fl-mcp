"""Persistence engine setup."""

from sqlmodel import SQLModel, create_engine

from fl_mcp.config.settings import settings

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Initialize local SQLite tables."""
    SQLModel.metadata.create_all(engine)
