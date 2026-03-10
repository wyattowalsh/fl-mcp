"""Canonical project graph structures."""

import json

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    kind: str = ""
    data: dict[str, object] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str = ""


def _canonical_payload(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _matches_domain(kind: str, domain: str) -> bool:
    return kind == domain or kind.startswith(f"{domain}.")


class ProjectGraph(BaseModel):
    schema_version: str = "1.0"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def to_projection(self, domain: str) -> dict[str, object]:
        projected_nodes = sorted(
            (node for node in self.nodes if _matches_domain(node.kind, domain)),
            key=lambda node: (node.id, node.kind, _canonical_payload(node.data)),
        )
        projected_node_ids = {node.id for node in projected_nodes}
        projected_edges = sorted(
            (
                edge
                for edge in self.edges
                if edge.source in projected_node_ids and edge.target in projected_node_ids
            ),
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.kind,
            ),
        )

        return {
            "domain": domain,
            "nodes": [node.model_dump() for node in projected_nodes],
            "edges": [edge.model_dump() for edge in projected_edges],
        }
