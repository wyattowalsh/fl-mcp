from fl_mcp.graph.model import GraphEdge, GraphNode, ProjectGraph


def test_graph_projection_roundtrip() -> None:
    graph = ProjectGraph(
        nodes=[
            GraphNode(id="2", kind="mixer.bus", data={"name": "bus"}),
            GraphNode(id="1", kind="mixer.channel", data={"name": "ch1"}),
            GraphNode(id="3", kind="patterns.clip", data={"name": "pat"}),
        ],
        edges=[
            GraphEdge(source="2", target="1", kind="routes"),
            GraphEdge(source="1", target="3", kind="cross-domain"),
            GraphEdge(source="1", target="2", kind="feeds"),
        ],
    )
    proj = graph.to_projection("mixer")
    assert proj["domain"] == "mixer"
    nodes = proj["nodes"]
    edges = proj["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert [node["id"] for node in nodes] == ["1", "2"]
    assert [edge["kind"] for edge in edges] == ["feeds", "routes"]
