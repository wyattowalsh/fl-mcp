"""Canonical project graph structures."""

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    kind: str
    data: dict[str, object] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str


class ProjectGraph(BaseModel):
    schema_version: str = "1.0"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def to_projection(self, domain: str) -> dict[str, object]:
        return {
            "domain": domain,
            "nodes": [n.model_dump() for n in self.nodes if n.kind.startswith(domain)],
            "edges": [e.model_dump() for e in self.edges],
        }
