"""Config shell command handlers."""

from __future__ import annotations

import argparse
import json


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    config_parser = subparsers.add_parser("config", help="Inspect and manage CLI config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    shell_parser = config_subparsers.add_parser("shell", help="Emit shell-ready config exports")
    shell_parser.add_argument(
        "--format",
        default="env",
        choices=("env", "json"),
        help="Format for shell exports",
    )
    shell_parser.set_defaults(handler=handle_config_shell)


def handle_config_shell(args: argparse.Namespace) -> int:
    config = {
        "FL_MCP_HOME": "~/.fl-mcp",
        "FL_MCP_TRANSPORT": "stdio",
    }
    if args.format == "json":
        print(json.dumps(config, indent=2))
    else:
        for key, value in config.items():
            print(f"export {key}={value}")
    return 0
