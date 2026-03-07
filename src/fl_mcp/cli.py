"""Unified CLI for launching FastMCP transports."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from fl_mcp.config import AppConfig, RuntimeConfig, StreamableHTTPConfig
from fl_mcp.logging import configure_logging
from fl_mcp.server.http import run_streamable_http
from fl_mcp.server.stdio import run_stdio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fl_mcp over stdio or streamable HTTP")
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--service-name", default="fl-mcp")
    parser.add_argument("--service-version", default="0.1.0")
    parser.add_argument("--log-level", default="INFO")

    subparsers = parser.add_subparsers(dest="transport", required=True)

    subparsers.add_parser("stdio", help="Run over stdio")

    http = subparsers.add_parser("streamable-http", help="Run streamable HTTP transport")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=8000)
    http.add_argument("--path", default="/mcp")

    return parser


def _runtime_config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    return RuntimeConfig(
        environment=args.environment,
        service_name=args.service_name,
        service_version=args.service_version,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    configure_logging(log_level)

    config = AppConfig.from_mapping(
        {
            "runtime": {
                "environment": args.environment,
                "service_name": args.service_name,
                "service_version": args.service_version,
            },
            "streamable_http": {
                "host": getattr(args, "host", "127.0.0.1"),
                "port": getattr(args, "port", 8000),
                "path": getattr(args, "path", "/mcp"),
            },
        }
    )

    if args.transport == "stdio":
        run_stdio(_runtime_config_from_args(args))
        return 0

    http_config = StreamableHTTPConfig(
        host=config.streamable_http.host,
        port=config.streamable_http.port,
        path=config.streamable_http.path,
    )
    run_streamable_http(config.runtime, http_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
