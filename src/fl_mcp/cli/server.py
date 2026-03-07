"""Server command handlers."""

from __future__ import annotations

import argparse
import json


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    server_parser = subparsers.add_parser("server", help="Manage FL MCP server runtime")
    server_subparsers = server_parser.add_subparsers(dest="server_command", required=True)

    run_parser = server_subparsers.add_parser("run", help="Run MCP server in stdio or http mode")
    run_parser.add_argument(
        "--mode",
        choices=("stdio", "http"),
        default="stdio",
        help="Transport mode for the server process",
    )
    run_parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP mode")
    run_parser.add_argument("--port", type=int, default=8765, help="Port for HTTP mode")
    run_parser.set_defaults(handler=handle_run)


def handle_run(args: argparse.Namespace) -> int:
    payload = {
        "action": "server.run",
        "mode": args.mode,
        "host": args.host,
        "port": args.port,
        "status": "scaffold-ready",
    }
    print(json.dumps(payload, indent=2))
    return 0
