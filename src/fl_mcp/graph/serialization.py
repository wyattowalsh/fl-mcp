"""Serialization helpers between project graphs and snapshot schemas."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fl_mcp.schemas.snapshots import GraphSnapshot, SnapshotMetadata

from .models import ProjectGraph


def serialize_snapshot(
    graph: ProjectGraph,
    snapshot_id: str,
    source_transaction_id: str | None = None,
) -> GraphSnapshot:
    """Serialize a graph into a canonical JSON snapshot."""

    canonical_json = json.dumps(graph.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    metadata = SnapshotMetadata(
        snapshot_id=snapshot_id,
        project_id=graph.project_id,
        created_at=datetime.now(timezone.utc),
        source_transaction_id=source_transaction_id,
    )
    return GraphSnapshot(metadata=metadata, graph_json=canonical_json)


def deserialize_snapshot(snapshot: GraphSnapshot) -> ProjectGraph:
    """Deserialize snapshot JSON back to a project graph."""

    return ProjectGraph.model_validate(json.loads(snapshot.graph_json))
