"""Canonical graph serialization utilities."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from fl_mcp.graph.model import GraphEdge, GraphNode, ProjectGraph

_SEPARATOR_TUPLE = (",", ":")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=_SEPARATOR_TUPLE)


def _normalize_nodes(raw_nodes: object) -> list[GraphNode]:
    if raw_nodes is None:
        return []
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, str | bytes | bytearray):
        raise ValueError("Graph 'nodes' must be a list of objects.")

    nodes: list[GraphNode] = []
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            raise ValueError("Graph node entries must be objects.")

        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("Graph node 'id' must be a non-empty string.")

        kind = node.get("kind", "")
        if kind is None:
            kind = ""
        if not isinstance(kind, str):
            raise ValueError("Graph node 'kind' must be a string.")

        data = node.get("data", {})
        if data is None:
            data = {}
        if not isinstance(data, Mapping):
            raise ValueError("Graph node 'data' must be an object if provided.")

        nodes.append(GraphNode(id=node_id, kind=kind, data=dict(data)))

    return sorted(
        nodes,
        key=lambda normalized: (
            normalized.id,
            normalized.kind,
            _canonical_json(normalized.data),
        ),
    )


def _normalize_edges(raw_edges: object) -> list[GraphEdge]:
    if raw_edges is None:
        return []
    if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, str | bytes | bytearray):
        raise ValueError("Graph 'edges' must be a list of objects.")

    edges: list[GraphEdge] = []
    for edge in raw_edges:
        if not isinstance(edge, Mapping):
            raise ValueError("Graph edge entries must be objects.")

        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not source:
            raise ValueError("Graph edge 'source' must be a non-empty string.")
        if not isinstance(target, str) or not target:
            raise ValueError("Graph edge 'target' must be a non-empty string.")

        kind = edge.get("kind", edge.get("type", ""))
        if kind is None:
            kind = ""
        if not isinstance(kind, str):
            raise ValueError("Graph edge 'kind' must be a string.")

        edges.append(GraphEdge(source=source, target=target, kind=kind))

    return sorted(
        edges,
        key=lambda normalized: (
            normalized.source,
            normalized.target,
            normalized.kind,
            _canonical_json(normalized.model_dump()),
        ),
    )


def _normalize_graph_payload(graph: Mapping[str, Any]) -> ProjectGraph:
    schema_version = graph.get("schema_version", "1.0")
    if not isinstance(schema_version, str):
        raise ValueError("Graph 'schema_version' must be a string if provided.")

    return ProjectGraph(
        schema_version=schema_version,
        nodes=_normalize_nodes(graph.get("nodes", [])),
        edges=_normalize_edges(graph.get("edges", [])),
    )


def serialize_graph(graph: dict[str, Any]) -> str:
    canonical_graph = _normalize_graph_payload(graph)
    canonical = {
        "schema_version": canonical_graph.schema_version,
        "nodes": [node.model_dump() for node in canonical_graph.nodes],
        "edges": [edge.model_dump() for edge in canonical_graph.edges],
    }
    return json.dumps(canonical, sort_keys=True, separators=_SEPARATOR_TUPLE)


def deserialize_graph(serialized: str) -> dict[str, Any]:
    decoded = json.loads(serialized)
    if not isinstance(decoded, Mapping):
        raise ValueError("Serialized graph must decode to an object.")

    canonical_graph = _normalize_graph_payload(decoded)
    return {
        "schema_version": canonical_graph.schema_version,
        "nodes": [node.model_dump() for node in canonical_graph.nodes],
        "edges": [edge.model_dump() for edge in canonical_graph.edges],
    }
