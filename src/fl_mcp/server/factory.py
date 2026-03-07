"""FastMCP 3.x server factory initialization."""

from __future__ import annotations

from typing import Any

from fl_mcp.config import RuntimeConfig
from fl_mcp.runtime.health import health_payload


def _load_fastmcp() -> type[Any]:
    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "FastMCP is required to run fl_mcp. Install a FastMCP 3.x compatible version."
        ) from exc
    return FastMCP


def create_server(runtime_config: RuntimeConfig) -> Any:
    """Create and initialize a FastMCP server instance."""

    FastMCP = _load_fastmcp()
    server = FastMCP(name=runtime_config.service_name)

    @server.resource("runtime://health")
    def runtime_health_resource() -> dict[str, str]:
        return health_payload(runtime_config)

    @server.tool(name="runtime_health", description="Get runtime health details.")
    def runtime_health_tool() -> dict[str, str]:
        return health_payload(runtime_config)

    return server
