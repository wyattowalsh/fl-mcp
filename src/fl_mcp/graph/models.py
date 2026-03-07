"""Canonical node/edge models for project graph state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    """Canonical graph node."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., description="Unique node identifier.")
    node_type: str = Field(..., description="Node type key.")
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Canonical directed graph edge."""

    model_config = ConfigDict(extra="forbid")

    source_node_id: str = Field(..., description="Source node ID.")
    target_node_id: str = Field(..., description="Target node ID.")
    edge_type: str = Field(..., description="Edge relationship type key.")
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProjectGraph(BaseModel):
    """Project-level graph snapshot payload."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
