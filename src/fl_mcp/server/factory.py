"""FastMCP 3.x server factory initialization."""

from __future__ import annotations

import json
from typing import Any, cast

from fl_mcp.config import RuntimeConfig
from fl_mcp.runtime.health import health_payload
from fl_mcp.tools import public

PUBLIC_TOOL_HANDLERS: dict[str, Any] = {
    "query_project": public.query_project,
    "plan_changes": public.plan_changes,
    "apply_changes": public.apply_changes,
    "render_project": public.render_project,
    "analyze_audio": public.analyze_audio,
    "inspect_runtime": public.inspect_runtime,
    "manage_providers": public.manage_providers,
}


class MinimalMCPServer:
    """Fallback server shell used when FastMCP is unavailable."""

    def __init__(self, runtime_config: RuntimeConfig) -> None:
        self.name = runtime_config.service_name
        self.resources: dict[str, Any] = {
            "runtime://health": lambda: _health_resource_payload(runtime_config),
        }
        self.tools: dict[str, Any] = {
            "runtime_health": lambda: health_payload(runtime_config),
            **PUBLIC_TOOL_HANDLERS,
        }


def _load_fastmcp() -> type[Any] | None:
    try:
        from fastmcp import FastMCP
    except ImportError:
        return None
    return cast(type[Any], FastMCP)


def create_server(runtime_config: RuntimeConfig) -> Any:
    """Create server instance, falling back to a local minimal shell."""

    fastmcp_cls = _load_fastmcp()
    if fastmcp_cls is None:
        return MinimalMCPServer(runtime_config)

    server = fastmcp_cls(name=runtime_config.service_name)

    def runtime_health_resource() -> str:
        return _health_resource_payload(runtime_config)

    server.resource("runtime://health")(runtime_health_resource)

    def runtime_health_tool() -> dict[str, str]:
        return health_payload(runtime_config)

    server.tool(name="runtime_health", description="Get runtime health details.")(
        runtime_health_tool
    )

    for name, handler in PUBLIC_TOOL_HANDLERS.items():
        server.tool(name=name)(handler)

    return server


def create_default_server() -> Any:
    """No-arg entrypoint for fastmcp.json bootstrap."""

    return create_server(RuntimeConfig())


def _health_resource_payload(runtime_config: RuntimeConfig) -> str:
    return json.dumps(health_payload(runtime_config), sort_keys=True)
