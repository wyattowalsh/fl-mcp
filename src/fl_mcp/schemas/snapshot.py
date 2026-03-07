"""Snapshot schemas."""

from pydantic import BaseModel, Field


class Snapshot(BaseModel):
    """Canonical graph snapshot."""

    snapshot_id: str
    version: int
    nodes: list[dict[str, object]] = Field(default_factory=list)
    edges: list[dict[str, object]] = Field(default_factory=list)
