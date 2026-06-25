"""Doctor command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp.bridge.bridge_diagnostics import collect_bridge_checks, diagnostic_context
from fl_mcp.interfaces.status import DiagnosticCheck, HealthState, HelperStatusPayload


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``doctor`` subcommand for environment diagnostics."""
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    doctor_parser.add_argument(
        "--format",
        default="table",
        choices=("table", "json"),
        help="Output format",
    )
    doctor_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with code 1 when aggregated health is WARNING (default: exit 0).",
    )
    doctor_parser.set_defaults(handler=handle_doctor)


def _aggregate_health(checks: list[DiagnosticCheck]) -> HealthState:
    if any(check.state is HealthState.ERROR for check in checks):
        return HealthState.ERROR
    if any(check.state is HealthState.WARNING for check in checks):
        return HealthState.WARNING
    return HealthState.OK


def handle_doctor(args: argparse.Namespace) -> int:
    """Run diagnostic checks and print results as a table or JSON."""
    ctx = diagnostic_context()
    checks = [
        DiagnosticCheck(
            name="python",
            state=HealthState.OK,
            details="Python runtime available",
        ),
        *collect_bridge_checks(),
    ]
    health = _aggregate_health(checks)
    status = HelperStatusPayload(
        health=health,
        checks=checks,
        logs=[
            "Doctor executed separate bridge checks: harness, controller byte-match, "
            "FL process probe, status freshness, host poll probe, and controller selection.",
            f"Harness command: {ctx.harness_command}",
            f"FL host bridge dir: {ctx.bridge_dir}",
            f"Selected-controller dir: {ctx.selected_controller_dir}",
        ],
    )

    exit_code = 1 if health is HealthState.ERROR else 0
    if getattr(args, "fail_on_warning", False) and health is HealthState.WARNING:
        exit_code = 1

    if args.format == "json":
        print(json.dumps(status.to_dict(), indent=2))
        return exit_code

    print("FL MCP Doctor")
    print("=============")
    print(f"Health: {status.health.value}")
    for check in status.checks:
        print(f"- {check.name}: {check.state.value} ({check.details})")
    return exit_code