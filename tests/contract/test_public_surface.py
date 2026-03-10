import asyncio
import json
from typing import cast

import pytest

import fl_mcp.server.factory as factory_module
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings


def test_public_tool_surface_is_sparse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect() -> tuple[set[str], set[str]]:
        if hasattr(server, "list_tools") and hasattr(server, "list_resources"):
            tools = await server.list_tools()
            resources = await server.list_resources()
            return (
                {tool.name for tool in tools},
                {str(resource.uri) for resource in resources},
            )

        return (
            set(server.tools.keys()),
            set(server.resources.keys()),
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


def test_runtime_health_resource_payload_is_json_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def read_health_resource() -> str:
        if hasattr(server, "read_resource"):
            result = await server.read_resource("runtime://health")
            return cast(str, result.contents[0].content)
        resource = server.resources["runtime://health"]
        return cast(str, resource())

    payload = json.loads(asyncio.run(read_health_resource()))
    assert payload["service"] == "fl-mcp"
    assert payload["status"] in {"ok", "warning", "error"}
