"""Install command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp.bridge.bundle import bridge_runner_descriptor


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``install`` subcommand for dependency management."""
    install_parser = subparsers.add_parser("install", help="Install dependencies and local assets")
    install_parser.add_argument(
        "--target",
        default="local",
        choices=("local", "system"),
        help="Installation target",
    )
    install_parser.add_argument(
        "--dry-run", action="store_true", help="Print install plan without executing"
    )
    install_parser.set_defaults(handler=handle_install)


def handle_install(args: argparse.Namespace) -> int:
    """Execute the install plan or print a dry-run summary."""
    descriptor = bridge_runner_descriptor()
    payload = {
        "action": "install",
        "target": args.target,
        "dry_run": args.dry_run,
        "status": "ready",
        "bridge": descriptor.model_dump(),
        "environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.command,
            "FL_MCP_FL_STUDIO_BRIDGE_DIR": descriptor.bridge_dir,
        },
        "harness_environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.harness_command,
        },
        "selected_controller_environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.selected_controller_command,
            "FL_MCP_SELECTED_CONTROLLER_DIR": descriptor.selected_controller_dir,
        },
        "uvx_server": {
            "stdio": "uvx fl-mcp server run --mode stdio",
            "http": "uvx fl-mcp server run --mode http",
        },
        "uvx_environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.uvx_command,
            "FL_MCP_FL_STUDIO_BRIDGE_DIR": descriptor.bridge_dir,
        },
        "uvx_harness_environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.uvx_harness_command,
        },
        "uvx_selected_controller_environment": {
            "FL_MCP_BRIDGE_MODE": "live",
            "FL_MCP_FL_STUDIO_BRIDGE_CMD": descriptor.uvx_selected_controller_command,
            "FL_MCP_SELECTED_CONTROLLER_DIR": descriptor.selected_controller_dir,
        },
        "fl_studio_controller": {
            "source": descriptor.controller_script,
            "target_dir": descriptor.hardware_script_dir,
            "target_file": f"{descriptor.hardware_script_dir}/device_FL_MCP_Bridge.py",
            "selection": "MIDI Settings > Controller type > FL MCP Bridge",
        },
    }
    print(json.dumps(payload, indent=2))
    return 0
