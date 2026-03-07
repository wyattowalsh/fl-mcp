from fl_mcp.graph.canonical import deserialize_graph, serialize_graph


def test_canonical_graph_serialization_roundtrip() -> None:
    graph = {
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [
            {"source": "b", "target": "a", "type": "depends_on"},
            {"source": "a", "target": "b", "type": "blocks"},
        ],
    }

    serialized = serialize_graph(graph)
    restored = deserialize_graph(serialized)

    assert [n["id"] for n in restored["nodes"]] == ["a", "b"]
    assert serialize_graph(restored) == serialized
