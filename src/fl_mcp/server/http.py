"""Streamable HTTP transport entrypoint for FastMCP."""

from __future__ import annotations

import logging

from fl_mcp.config import RuntimeConfig, StreamableHTTPConfig
from fl_mcp.server.factory import create_server

LOGGER = logging.getLogger(__name__)


def _run_streamable_http(server: object, config: StreamableHTTPConfig) -> None:
    run_streamable_http = getattr(server, "run_streamable_http", None)
    if callable(run_streamable_http):
        run_streamable_http(host=config.host, port=config.port, path=config.path)
        return
    run = getattr(server, "run", None)
    if callable(run):
        run(
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
