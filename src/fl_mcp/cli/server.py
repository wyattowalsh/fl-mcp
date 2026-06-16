"""Server command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp import __version__
from fl_mcp.config import RuntimeConfig, StreamableHTTPConfig
from fl_mcp.config.settings import settings
from fl_mcp.logging import configure_logging
from fl_mcp.server.http import run_streamable_http
from fl_mcp.server.stdio import run_stdio


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``server`` subcommand for managing the MCP server runtime."""
    server_parser = subparsers.add_parser("server", help="Manage FL MCP server runtime")
    server_subparsers = server_parser.add_subparsers(dest="server_command", required=True)

    run_parser = server_subparsers.add_parser("run", help="Run MCP server in stdio or http mode")
    run_parser.add_argument(
        "--mode",
        choices=("stdio", "http"),
        default="stdio",
        help="Transport mode for the server process",
    )
    run_parser.add_argument("--environment", default="dev", help="Runtime environment name")
    run_parser.add_argument("--service-name", default="fl-mcp", help="Service name for telemetry")
    run_parser.add_argument(
        "--service-version", default=__version__, help="Service version for telemetry"
    )
    run_parser.add_argument("--log-level", default="INFO", help="Root log level")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Emit config only without launching"
    )
    run_parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP mode")
    run_parser.add_argument("--port", type=int, default=8765, help="Port for HTTP mode")
    run_parser.add_argument("--path", default="/mcp", help="Path for streamable HTTP mode")
    run_parser.set_defaults(handler=handle_run)


def handle_run(args: argparse.Namespace) -> int:
    """Launch the MCP server in stdio or streamable-HTTP mode."""
    runtime = RuntimeConfig(
        environment=args.environment,
        service_name=args.service_name,
        service_version=args.service_version,
    )
    http = StreamableHTTPConfig(host=args.host, port=args.port, path=args.path)

    payload = {
        "action": "server.run",
        "mode": args.mode,
        "runtime": {
            "environment": runtime.environment,
            "service_name": runtime.service_name,
            "service_version": runtime.service_version,
            "surface": "compact",
        },
        "http": {
            "host": http.host,
            "port": http.port,
            "path": http.path,
        },
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    production_http_without_auth = (
        args.mode == "http"
        and runtime.environment in {"prod", "production"}
        and not settings.auth_token
    )
    if production_http_without_auth:
        print(
            "FL_MCP_AUTH_TOKEN is required for production HTTP mode.",
            flush=True,
        )
        return 2

    configure_logging(args.log_level)
    if args.mode == "stdio":
        run_stdio(runtime)
    else:
        run_streamable_http(runtime, http)

    return 0
