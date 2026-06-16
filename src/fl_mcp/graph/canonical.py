"""Canonical graph serialization utilities."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

_SEPARATOR_TUPLE = (",", ":")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=_SEPARATOR_TUPLE)


def _normalize_nodes(raw_nodes: object) -> list[dict[str, object]]:
    if raw_nodes is None:
        return []
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, str | bytes | bytearray):
        raise ValueError("Graph 'nodes' must be a list of objects.")

    nodes: list[dict[str, object]] = []
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

        nodes.append({"id": node_id, "kind": kind, "data": dict(data)})

    return sorted(
        nodes,
        key=lambda normalized: (
            str(normalized["id"]),
            str(normalized["kind"]),
            _canonical_json(normalized["data"]),
        ),
    )


def _normalize_edges(raw_edges: object) -> list[dict[str, str]]:
    if raw_edges is None:
        return []
    if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, str | bytes | bytearray):
        raise ValueError("Graph 'edges' must be a list of objects.")

    edges: list[dict[str, str]] = []
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

        edges.append({"source": source, "target": target, "kind": kind})

    return sorted(
        edges,
        key=lambda normalized: (
            normalized["source"],
            normalized["target"],
            normalized["kind"],
            _canonical_json(normalized),
        ),
    )


def _normalize_graph_payload(graph: Mapping[str, object]) -> dict[str, object]:
    schema_version = graph.get("schema_version", "1.0")
    if not isinstance(schema_version, str):
        raise ValueError("Graph 'schema_version' must be a string if provided.")

    return {
        "schema_version": schema_version,
        "nodes": _normalize_nodes(graph.get("nodes", [])),
        "edges": _normalize_edges(graph.get("edges", [])),
    }


def serialize_graph(graph: dict[str, object]) -> str:
    """Normalize and serialize a graph dict to a deterministic JSON string.

    Args:
        graph: Raw graph payload with nodes and edges.

    Returns:
        Canonical compact JSON representation.

    Raises:
        ValueError: If the graph structure is invalid.
    """
    canonical_graph = _normalize_graph_payload(graph)
    return json.dumps(canonical_graph, sort_keys=True, separators=_SEPARATOR_TUPLE)


def deserialize_graph(serialized: str) -> dict[str, object]:
    """Deserialize a canonical JSON string back into a normalized graph dict.

    Args:
        serialized: JSON string produced by ``serialize_graph``.

    Returns:
        Normalized graph payload with sorted nodes and edges.

    Raises:
        ValueError: If the serialized data is not a valid graph object.
    """
    decoded = json.loads(serialized)
    if not isinstance(decoded, Mapping):
        raise ValueError("Serialized graph must decode to an object.")

    return _normalize_graph_payload(decoded)
