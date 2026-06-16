"""Canonical project graph structures."""

import json

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A single node in the project graph."""

    id: str
    kind: str = ""
    data: dict[str, object] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge connecting two nodes in the project graph."""

    source: str
    target: str
    kind: str = ""


def _canonical_payload(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _matches_domain(kind: str, domain: str) -> bool:
    return kind == domain or kind.startswith(f"{domain}.")


class ProjectGraph(BaseModel):
    """Canonical project graph containing typed nodes and directed edges."""

    schema_version: str = "1.0"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def to_projection(self, domain: str) -> dict[str, object]:
        """Project the graph to a single domain, returning matching nodes and edges.

        Args:
            domain: Domain name to filter nodes by kind prefix.

        Returns:
            Dict with 'domain', 'nodes', and 'edges' keys for the projection.
        """
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
