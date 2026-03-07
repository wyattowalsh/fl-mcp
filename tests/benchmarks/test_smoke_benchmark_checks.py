from __future__ import annotations

from time import perf_counter

from fl_mcp.graph.canonical import serialize_graph


def test_canonical_graph_serialization_smoke_benchmark() -> None:
    graph = {
        "nodes": [{"id": str(i)} for i in range(250)],
        "edges": [{"source": str(i), "target": str(i + 1), "type": "link"} for i in range(249)],
    }

    start = perf_counter()
    for _ in range(50):
        serialize_graph(graph)
    elapsed = perf_counter() - start

    assert elapsed < 1.0
