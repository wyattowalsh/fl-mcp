"""Bridge and FL Studio environment diagnostics for ``fl-mcp doctor``."""

from __future__ import annotations

import filecmp
import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from fl_mcp.bridge.bundle import (
    bridge_runner_descriptor,
    controller_script_path,
    default_file_bridge_dir,
    default_hardware_script_dir,
    run_harness_smoke,
)
from fl_mcp.bridge.host_client import STATUS_FILE_NAME, ensure_private_bridge_dir
from fl_mcp.interfaces.status import DiagnosticCheck, HealthState

STATUS_FRESHNESS_SECONDS = 30.0
FL_PROCESS_NAME = "OsxFL"


@dataclass(slots=True)
class BridgeDiagnosticContext:
    """Resolved paths and environment used by doctor checks."""

    controller_source: Path
    controller_target: Path
    bridge_dir: Path
    harness_command: str
    selected_controller_command: str
    selected_controller_dir: str


def diagnostic_context() -> BridgeDiagnosticContext:
    """Build the path context shared by doctor bridge checks."""

    descriptor = bridge_runner_descriptor()
    return BridgeDiagnosticContext(
        controller_source=controller_script_path().expanduser().resolve(),
        controller_target=default_hardware_script_dir() / "device_FL_MCP_Bridge.py",
        bridge_dir=default_file_bridge_dir().expanduser(),
        harness_command=descriptor.harness_command,
        selected_controller_command=descriptor.selected_controller_command,
        selected_controller_dir=descriptor.selected_controller_dir,
    )


def _read_status_snapshot(bridge_dir: Path) -> dict[str, object] | None:
    status_path = bridge_dir / STATUS_FILE_NAME
    if not status_path.is_file():
        return None
    try:
        decoded = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(status_path), "read_error": "status.json is unreadable"}
    if not isinstance(decoded, dict):
        return {"path": str(status_path), "read_error": "status.json did not contain an object"}
    snapshot = {str(key): value for key, value in decoded.items()}
    snapshot["path"] = str(status_path)
    updated_at = snapshot.get("updated_at")
    if isinstance(updated_at, int | float):
        snapshot["age_seconds"] = max(0.0, time.time() - float(updated_at))
    return snapshot


def check_harness() -> DiagnosticCheck:
    """Run packaged harness read/mutation smoke."""

    smoke = run_harness_smoke()
    ok = smoke.get("ok") is True
    return DiagnosticCheck(
        name="bridge-harness",
        state=HealthState.OK if ok else HealthState.WARNING,
        details=json.dumps(smoke, sort_keys=True),
    )


def check_controller_byte_match(ctx: BridgeDiagnosticContext) -> DiagnosticCheck:
    """Verify the installed FL Studio controller script byte-matches the bundle."""

    source = ctx.controller_source
    target = ctx.controller_target
    if not source.is_file():
        return DiagnosticCheck(
            name="controller-byte-match",
            state=HealthState.ERROR,
            details=(
                f"Bundled controller script missing at {source}. "
                "Remediation: reinstall fl-mcp from a release that includes fl-bundle/controller."
            ),
        )
    if not target.is_file():
        return DiagnosticCheck(
            name="controller-byte-match",
            state=HealthState.WARNING,
            details=(
                f"Installed controller script not found at {target}. "
                "Remediation: run `fl-mcp install --sync-controller` then select "
                "FL MCP Bridge in FL Studio MIDI Settings."
            ),
        )
    if filecmp.cmp(source, target, shallow=False):
        return DiagnosticCheck(
            name="controller-byte-match",
            state=HealthState.OK,
            details=f"Installed script matches bundled source ({source.name}).",
        )
    return DiagnosticCheck(
        name="controller-byte-match",
        state=HealthState.WARNING,
        details=(
            f"Installed script at {target} differs from bundled source at {source}. "
            "Remediation: run `fl-mcp install --sync-controller` to refresh with backup."
        ),
    )


def check_fl_process() -> DiagnosticCheck:
    """Report whether the FL Studio process appears to be running (macOS optional)."""

    if platform.system() != "Darwin":
        return DiagnosticCheck(
            name="fl-studio-process",
            state=HealthState.OK,
            details=(
                "FL Studio process probe is optional on this platform. "
                "Remediation: ensure FL Studio is open before attempting live bridge calls."
            ),
        )

    if shutil.which("pgrep") is None:
        return DiagnosticCheck(
            name="fl-studio-process",
            state=HealthState.OK,
            details=(
                "pgrep is unavailable; skipped OsxFL process probe. "
                "Remediation: launch FL Studio manually before live bridge checks."
            ),
        )

    try:
        completed = subprocess.run(
            ["pgrep", "-x", FL_PROCESS_NAME],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DiagnosticCheck(
            name="fl-studio-process",
            state=HealthState.WARNING,
            details=(
                f"Could not probe FL Studio process: {exc}. "
                "Remediation: launch FL Studio and re-run `fl-mcp doctor`."
            ),
        )

    if completed.returncode == 0 and completed.stdout.strip():
        pids = completed.stdout.strip().splitlines()
        return DiagnosticCheck(
            name="fl-studio-process",
            state=HealthState.OK,
            details=f"Detected FL Studio process {FL_PROCESS_NAME} (pids: {', '.join(pids)}).",
        )
    return DiagnosticCheck(
        name="fl-studio-process",
        state=HealthState.WARNING,
        details=(
            f"FL Studio process {FL_PROCESS_NAME} is not running. "
            "Remediation: open FL Studio, select FL MCP Bridge in MIDI Settings, "
            "then re-run doctor."
        ),
    )


def check_status_freshness(ctx: BridgeDiagnosticContext) -> DiagnosticCheck:
    """Warn when bridge status.json is missing or stale."""

    snapshot = _read_status_snapshot(ctx.bridge_dir)
    if snapshot is None:
        return DiagnosticCheck(
            name="status-freshness",
            state=HealthState.WARNING,
            details=(
                f"No status.json at {ctx.bridge_dir / STATUS_FILE_NAME}. "
                "Remediation: select FL MCP Bridge in FL Studio MIDI Settings so the "
                "controller script creates and refreshes status.json."
            ),
        )
    if snapshot.get("read_error"):
        return DiagnosticCheck(
            name="status-freshness",
            state=HealthState.WARNING,
            details=(
                f"Could not read status.json: {snapshot['read_error']}. "
                "Remediation: confirm bridge directory permissions and controller selection."
            ),
        )

    age_seconds = snapshot.get("age_seconds")
    if not isinstance(age_seconds, int | float):
        return DiagnosticCheck(
            name="status-freshness",
            state=HealthState.WARNING,
            details=(
                "status.json is present but missing updated_at age metadata. "
                "Remediation: restart FL Studio with FL MCP Bridge selected."
            ),
        )

    if float(age_seconds) <= STATUS_FRESHNESS_SECONDS:
        return DiagnosticCheck(
            name="status-freshness",
            state=HealthState.OK,
            details=(
                f"status.json refreshed {float(age_seconds):.1f}s ago "
                f"(threshold {STATUS_FRESHNESS_SECONDS:.0f}s)."
            ),
        )
    return DiagnosticCheck(
        name="status-freshness",
        state=HealthState.WARNING,
        details=(
            f"status.json is stale ({float(age_seconds):.1f}s old). "
            "Remediation: ensure FL MCP Bridge is the active MIDI controller and FL Studio "
            "is polling the bridge directory."
        ),
    )


def check_host_poll_probe(ctx: BridgeDiagnosticContext) -> DiagnosticCheck:
    """Verify the bridge directory is private and ready for host polling."""

    try:
        secured = ensure_private_bridge_dir(ctx.bridge_dir)
    except ValueError as exc:
        return DiagnosticCheck(
            name="host-poll-probe",
            state=HealthState.ERROR,
            details=(
                f"Bridge directory failed security checks: {exc} "
                "Remediation: remove symlinks, fix ownership, and chmod 0700 on the bridge dir."
            ),
        )

    snapshot = _read_status_snapshot(secured)
    poll_reason = snapshot.get("poll_reason") if snapshot else None
    processed = snapshot.get("processed_request_count") if snapshot else None
    age_seconds = snapshot.get("age_seconds") if snapshot else None
    if isinstance(age_seconds, int | float):
        age = float(age_seconds)
        if age <= STATUS_FRESHNESS_SECONDS:
            return DiagnosticCheck(
                name="host-poll-probe",
                state=HealthState.OK,
                details=(
                    f"Bridge dir {secured} is secure and host polling is active "
                    f"(poll_reason={poll_reason!r}, processed_request_count={processed!r})."
                ),
            )

    return DiagnosticCheck(
        name="host-poll-probe",
        state=HealthState.WARNING,
        details=(
            f"Bridge dir {secured} is secure but no recent host poll heartbeat was observed. "
            "Remediation: open FL Studio, select FL MCP Bridge, and confirm status.json "
            "updated_at advances every few seconds."
        ),
    )


def check_controller_selection_hint(ctx: BridgeDiagnosticContext) -> DiagnosticCheck:
    """Provide controller-selection guidance based on install and status signals."""

    target_exists = ctx.controller_target.is_file()
    snapshot = _read_status_snapshot(ctx.bridge_dir)
    fresh = False
    age_seconds = snapshot.get("age_seconds") if snapshot else None
    if isinstance(age_seconds, int | float):
        fresh = float(age_seconds) <= STATUS_FRESHNESS_SECONDS

    if target_exists and fresh:
        return DiagnosticCheck(
            name="controller-selection",
            state=HealthState.OK,
            details=(
                "FL MCP Bridge appears installed and polling. "
                f"Active bridge dir: {ctx.bridge_dir}."
            ),
        )

    hints: list[str] = []
    if not target_exists:
        hints.append("run `fl-mcp install --sync-controller`")
    if not fresh:
        hints.append("select FL MCP Bridge in FL Studio MIDI Settings > Controller type")
    hints.append(f"set FL_MCP_FL_STUDIO_BRIDGE_DIR={ctx.bridge_dir}")
    hints.append(
        "or use the selected-controller adapter via "
        f"FL_MCP_FL_STUDIO_BRIDGE_CMD={ctx.selected_controller_command}"
    )

    return DiagnosticCheck(
        name="controller-selection",
        state=HealthState.WARNING if hints else HealthState.OK,
        details="Remediation: " + "; ".join(hints) + ".",
    )


def collect_bridge_checks() -> list[DiagnosticCheck]:
    """Return the ordered doctor checks for bridge readiness."""

    ctx = diagnostic_context()
    return [
        DiagnosticCheck(
            name="bundle",
            state=HealthState.OK,
            details=f"Bridge runner harness command: {ctx.harness_command}",
        ),
        check_harness(),
        check_controller_byte_match(ctx),
        check_fl_process(),
        check_status_freshness(ctx),
        check_host_poll_probe(ctx),
        check_controller_selection_hint(ctx),
        DiagnosticCheck(
            name="selected-controller-adapter",
            state=HealthState.OK,
            details=(
                "Selected-controller command: "
                f"{ctx.selected_controller_command}; directory: {ctx.selected_controller_dir}"
            ),
        ),
    ]