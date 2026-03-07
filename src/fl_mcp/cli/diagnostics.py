"""Diagnostics shell command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp.interfaces.status import (
    HELPER_DIAGNOSTICS_ENDPOINT,
    HELPER_STATUS_ENDPOINT,
    DiagnosticCheck,
    HealthState,
    HelperStatusPayload,
)


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    diagnostics_parser = subparsers.add_parser(
        "diagnostics", help="Status and diagnostics shell integrations"
    )
    diagnostics_subparsers = diagnostics_parser.add_subparsers(
        dest="diagnostics_command", required=True
    )

    shell_parser = diagnostics_subparsers.add_parser(
        "shell", help="Emit diagnostics payload for shell and helper app"
    )
    shell_parser.add_argument(
        "--endpoint",
        choices=("status", "diagnostics"),
        default="status",
        help="Target helper endpoint payload shape",
    )
    shell_parser.set_defaults(handler=handle_diagnostics_shell)


def handle_diagnostics_shell(args: argparse.Namespace) -> int:
    payload = HelperStatusPayload(
        checks=[
            DiagnosticCheck(
                name="cli",
                state=HealthState.OK,
                details="CLI diagnostics endpoint operational",
            )
        ],
        logs=["diagnostics.shell invoked"],
    ).to_dict()

    payload["endpoint"] = (
        HELPER_STATUS_ENDPOINT if args.endpoint == "status" else HELPER_DIAGNOSTICS_ENDPOINT
    )
    print(json.dumps(payload, indent=2))
    return 0
