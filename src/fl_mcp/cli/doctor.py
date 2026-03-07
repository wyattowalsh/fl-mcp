"""Doctor command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp.interfaces.status import DiagnosticCheck, HealthState, HelperStatusPayload


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    doctor_parser.add_argument(
        "--format",
        default="table",
        choices=("table", "json"),
        help="Output format",
    )
    doctor_parser.set_defaults(handler=handle_doctor)


def handle_doctor(args: argparse.Namespace) -> int:
    status = HelperStatusPayload(
        health=HealthState.OK,
        checks=[
            DiagnosticCheck(
                name="python",
                state=HealthState.OK,
                details="Python runtime available",
            ),
            DiagnosticCheck(
                name="bundle",
                state=HealthState.WARNING,
                details="FL bundle scaffold present; concrete assets pending",
            ),
        ],
        logs=["Doctor scaffold executed"],
    )

    if args.format == "json":
        print(json.dumps(status.to_dict(), indent=2))
        return 0

    print("FL MCP Doctor")
    print("=============")
    print(f"Health: {status.health.value}")
    for check in status.checks:
        print(f"- {check.name}: {check.state.value} ({check.details})")
    return 0
