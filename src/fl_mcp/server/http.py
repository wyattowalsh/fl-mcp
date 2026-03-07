"""Streamable HTTP transport entrypoint for FastMCP."""

from __future__ import annotations

import logging
from typing import Any

from fl_mcp.config import RuntimeConfig, StreamableHTTPConfig
from fl_mcp.server.factory import create_server

LOGGER = logging.getLogger(__name__)


def _run_streamable_http(server: Any, config: StreamableHTTPConfig) -> None:
    if hasattr(server, "run_streamable_http"):
        server.run_streamable_http(host=config.host, port=config.port, path=config.path)
        return
    if hasattr(server, "run"):
        server.run(
            transport="streamable-http",
            host=config.host,
            port=config.port,
            path=config.path,
        )
        return
    raise RuntimeError("FastMCP server does not expose streamable HTTP run methods.")


def run_streamable_http(runtime_config: RuntimeConfig, config: StreamableHTTPConfig) -> None:
    server = create_server(runtime_config)
    LOGGER.info(
        "Starting FastMCP streamable HTTP server",
        extra={
            "event": "server_startup",
            "transport": "streamable-http",
            "host": config.host,
            "port": config.port,
            "path": config.path,
            "service": runtime_config.service_name,
            "version": runtime_config.service_version,
            "environment": runtime_config.environment,
        },
    )
    _run_streamable_http(server, config)
