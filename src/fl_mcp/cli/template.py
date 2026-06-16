"""Template recipe command handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fl_mcp.bridge.selected_controller_client import (
    DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
    SelectedControllerClient,
)
from fl_mcp.recipes.hardstyle_template import build_hardstyle_template


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``template`` subcommand for FL Studio project recipes."""

    template_parser = subparsers.add_parser("template", help="Run FL Studio template recipes")
    template_subparsers = template_parser.add_subparsers(
        dest="template_command",
        required=True,
    )

    hardstyle_parser = template_subparsers.add_parser(
        "hardstyle",
        help="Preflight the oldschool hardstyle template build",
    )
    hardstyle_parser.add_argument("--controller-dir", type=Path, default=None)
    hardstyle_parser.add_argument("--audit-dir", type=Path, default=None)
    hardstyle_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
        help="Selected-controller response timeout in seconds",
    )
    hardstyle_parser.add_argument("--poll-interval", type=float, default=None)
    hardstyle_parser.add_argument("--allow-current-project-edits", action="store_true")
    hardstyle_parser.set_defaults(handler=handle_hardstyle)


def handle_hardstyle(args: argparse.Namespace) -> int:
    """Run the hardstyle template recipe preflight."""

    client = SelectedControllerClient(
        controller_dir=args.controller_dir,
        timeout_seconds=args.timeout,
        poll_interval_seconds=args.poll_interval,
    )
    run = build_hardstyle_template(
        client=client,
        audit_dir=args.audit_dir,
        allow_current_project_edits=args.allow_current_project_edits,
    )
    print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
    return 2 if run.status == "blocked" else 0
