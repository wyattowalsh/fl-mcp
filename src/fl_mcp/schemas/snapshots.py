"""Snapshot schemas for serialized project graph states."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SnapshotMetadata(BaseModel):
    """Metadata associated with a project graph snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(..., description="Unique snapshot identifier.")
    project_id: str = Field(..., description="Project that owns the snapshot.")
    created_at: datetime = Field(..., description="Snapshot creation timestamp in UTC.")
    source_transaction_id: str | None = Field(
        None,
        description="Transaction that produced this snapshot, if any.",
    )


class GraphSnapshot(BaseModel):
    """Serialized graph snapshot payload."""

    model_config = ConfigDict(extra="forbid")

    metadata: SnapshotMetadata
    graph_json: str = Field(..., description="Canonical JSON string representation of the project graph.")
