"""Stdio transport entrypoint for FastMCP."""

from __future__ import annotations

import logging
from typing import Any

from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import create_server

LOGGER = logging.getLogger(__name__)


def _run_stdio(server: Any) -> None:
    if hasattr(server, "run_stdio"):
        server.run_stdio()
        return
    if hasattr(server, "run"):
        server.run(transport="stdio")
        return
    raise RuntimeError("FastMCP server does not expose stdio run methods.")


def run_stdio(runtime_config: RuntimeConfig) -> None:
    server = create_server(runtime_config)
    LOGGER.info(
        "Starting FastMCP stdio server",
        extra={
            "event": "server_startup",
            "transport": "stdio",
            "service": runtime_config.service_name,
            "version": runtime_config.service_version,
            "environment": runtime_config.environment,
        },
    )
    _run_stdio(server)
