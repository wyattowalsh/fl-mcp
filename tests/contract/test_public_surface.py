import asyncio
import json
from typing import cast

from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import create_server


def test_public_tool_surface_is_sparse() -> None:
    server = create_server(RuntimeConfig())

    async def inspect() -> tuple[set[str], set[str]]:
        tools = await server.list_tools()
        resources = await server.list_resources()
        return (
            {tool.name for tool in tools},
            {str(resource.uri) for resource in resources},
        )

    tool_names, resource_uris = asyncio.run(inspect())

    assert tool_names == {
        "runtime_health",
        "query_project",
        "plan_changes",
        "apply_changes",
        "render_project",
        "analyze_audio",
        "inspect_runtime",
        "manage_providers",
    }
    assert resource_uris == {"runtime://health"}


def test_runtime_health_resource_payload_is_json_text() -> None:
    server = create_server(RuntimeConfig())

    async def read_health_resource() -> str:
        result = await server.read_resource("runtime://health")
        return cast(str, result.contents[0].content)

    payload = json.loads(asyncio.run(read_health_resource()))
    assert payload["service"] == "fl-mcp"
    assert payload["status"] in {"ok", "warning", "error"}
