from typing import cast

import pytest

from fl_mcp.graph.canonical import deserialize_graph, serialize_graph


def test_canonical_graph_serialization_roundtrip() -> None:
    graph: dict[str, object] = {
        "schema_version": "2.1",
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [
            {"source": "b", "target": "a", "type": "depends_on"},
            {"source": "a", "target": "b", "type": "blocks"},
        ],
    }

    serialized = serialize_graph(graph)
    restored = deserialize_graph(serialized)
    restored_nodes = cast(list[dict[str, object]], restored["nodes"])
    restored_edges = cast(list[dict[str, object]], restored["edges"])

    assert [n["id"] for n in restored_nodes] == ["a", "b"]
    assert restored["schema_version"] == "2.1"
    assert [n["kind"] for n in restored_nodes] == ["", ""]
    assert [e["kind"] for e in restored_edges] == ["blocks", "depends_on"]
    assert serialize_graph(restored) == serialized


def test_canonical_graph_serialization_is_deterministic_for_kind_edges() -> None:
    graph_a: dict[str, object] = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"source": "a", "target": "b", "kind": "z"},
            {"source": "a", "target": "b", "kind": "a"},
        ],
    }
    graph_b: dict[str, object] = {
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [
            {"source": "a", "target": "b", "kind": "a"},
            {"source": "a", "target": "b", "kind": "z"},
        ],
    }

    assert serialize_graph(graph_a) == serialize_graph(graph_b)


def test_canonical_graph_serialization_is_deterministic_for_duplicate_node_ids() -> None:
    graph_a: dict[str, object] = {
        "nodes": [
            {"id": "node-1", "kind": "mixer.track", "data": {"name": "alpha"}},
            {"id": "node-1", "kind": "mixer.track", "data": {"name": "beta"}},
        ],
        "edges": [],
    }
    graph_b: dict[str, object] = {
        "nodes": [
            {"id": "node-1", "kind": "mixer.track", "data": {"name": "beta"}},
            {"id": "node-1", "kind": "mixer.track", "data": {"name": "alpha"}},
        ],
        "edges": [],
    }

    assert serialize_graph(graph_a) == serialize_graph(graph_b)


def test_canonical_graph_serialization_normalizes_kind_and_type_edges() -> None:
    graph_with_type: dict[str, object] = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b", "type": "depends_on"}],
    }
    graph_with_kind: dict[str, object] = {
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [{"source": "a", "target": "b", "kind": "depends_on"}],
    }

    assert serialize_graph(graph_with_type) == serialize_graph(graph_with_kind)


def test_deserialize_graph_rejects_invalid_payload_shape() -> None:
    with pytest.raises(ValueError, match="must decode to an object"):
        deserialize_graph("[]")

    with pytest.raises(ValueError, match="non-empty string"):
        deserialize_graph('{"nodes":[{"id":""}],"edges":[]}')


def test_deserialize_graph_defaults_schema_version_when_missing() -> None:
    restored = deserialize_graph('{"nodes":[{"id":"a"}],"edges":[]}')
    assert restored["schema_version"] == "1.0"
