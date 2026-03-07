from fl_mcp.server.app import create_server


def test_public_tool_surface_is_sparse() -> None:
    server = create_server()
    assert set(server.tools.keys()) == {
        "query_project",
        "plan_changes",
        "apply_changes",
        "render_project",
        "analyze_audio",
        "inspect_runtime",
        "manage_providers",
    }
