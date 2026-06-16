"""Doctor command handlers."""

from __future__ import annotations

import argparse
import json

from fl_mcp.bridge.bundle import bridge_runner_descriptor, run_harness_smoke
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
    doctor_parser.set_defaults(handler=handle_doctor)


def handle_doctor(args: argparse.Namespace) -> int:
    """Run diagnostic checks and print results as a table or JSON."""
    bridge_descriptor = bridge_runner_descriptor()
    harness_smoke = run_harness_smoke()
    harness_ok = harness_smoke.get("ok") is True
    health = HealthState.OK if harness_ok else HealthState.WARNING
    status = HelperStatusPayload(
        health=health,
        checks=[
            DiagnosticCheck(
                name="python",
                state=HealthState.OK,
                details="Python runtime available",
            ),
            DiagnosticCheck(
                name="bundle",
                state=HealthState.OK,
                details=f"Bridge runner command: {bridge_descriptor.command}",
            ),
            DiagnosticCheck(
                name="fl-host-script",
                state=HealthState.OK,
                details=(
                    "Install "
                    f"{bridge_descriptor.controller_script} to "
                    f"{bridge_descriptor.hardware_script_dir} and select FL MCP Bridge "
                    "in FL Studio MIDI Settings."
                ),
            ),
            DiagnosticCheck(
                name="selected-controller-adapter",
                state=HealthState.OK,
                details=(
                    "Selected-controller command: "
                    f"{bridge_descriptor.selected_controller_command}; "
                    f"directory: {bridge_descriptor.selected_controller_dir}"
                ),
            ),
            DiagnosticCheck(
                name="bridge-harness",
                state=HealthState.OK if harness_ok else HealthState.WARNING,
                details=json.dumps(harness_smoke, sort_keys=True),
            ),
        ],
        logs=[
            "Doctor executed packaged bridge harness read/mutation smoke.",
            f"Harness command: {bridge_descriptor.harness_command}",
            f"FL host bridge dir: {bridge_descriptor.bridge_dir}",
            f"Selected-controller dir: {bridge_descriptor.selected_controller_dir}",
        ],
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
