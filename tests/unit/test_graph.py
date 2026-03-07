from fl_mcp.graph.model import GraphEdge, GraphNode, ProjectGraph


def test_graph_projection_roundtrip() -> None:
    graph = ProjectGraph(
        nodes=[GraphNode(id="1", kind="mixer.channel", data={"name": "ch1"})],
        edges=[GraphEdge(source="1", target="1", kind="self")],
    )
    proj = graph.to_projection("mixer")
    assert proj["domain"] == "mixer"
    assert len(proj["nodes"]) == 1
