"""Helpers for the repo-owned FL Studio bridge bundle."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from fl_mcp.bridge.fl_studio import FLStudioBridge
from fl_mcp.schemas.bridge import BridgeRunnerModeResponse

CONTROLLER_SCRIPT_RELATIVE_PATH = Path("fl-bundle/controller/device_FL_MCP_Bridge.py")
_FL_USER_DATA_RELATIVE_PATHS = (
    Path("Documents/Image-Line/FL Studio"),
    Path("Documents/Image-Line 2/FL Studio"),
)
UVX_PACKAGE_SPEC = "fl-mcp"


def bridge_runner_argv(*, harness: bool = False, live: bool = True) -> list[str]:
    """Return argv for the packaged bridge runner."""
    mode = "harness" if harness else ("live" if live else "auto")
    return [sys.executable, "-m", "fl_mcp.bridge.runner", "--mode", mode]


def bridge_runner_command(*, harness: bool = False, live: bool = True) -> str:
    """Return a shell-safe command string for ``FL_MCP_FL_STUDIO_BRIDGE_CMD``."""
    return shlex.join(bridge_runner_argv(harness=harness, live=live))


def uvx_argv(*args: str, package_spec: str = UVX_PACKAGE_SPEC) -> list[str]:
    """Return argv for running a command from an uvx-installed package."""

    return ["uvx", "--from", package_spec, *args]


def uvx_command(*args: str, package_spec: str = UVX_PACKAGE_SPEC) -> str:
    """Return a shell-safe uvx command string."""

    return shlex.join(uvx_argv(*args, package_spec=package_spec))


def file_bridge_argv() -> list[str]:
    """Return argv for the MCP-side FL host file bridge client."""

    return [sys.executable, "-m", "fl_mcp.bridge.host_client"]


def file_bridge_command() -> str:
    """Return a shell-safe command string for the FL host file bridge client."""

    return shlex.join(file_bridge_argv())


def uvx_file_bridge_command(*, package_spec: str = UVX_PACKAGE_SPEC) -> str:
    """Return a stable uvx command for the FL host file bridge client."""

    return uvx_command("python", "-m", "fl_mcp.bridge.host_client", package_spec=package_spec)


def selected_controller_argv() -> list[str]:
    """Return argv for the selected-controller compatibility bridge client."""

    return [sys.executable, "-m", "fl_mcp.bridge.selected_controller_client"]


def selected_controller_command() -> str:
    """Return a shell-safe command string for the selected-controller bridge."""

    return shlex.join(selected_controller_argv())


def uvx_bridge_runner_command(
    *, harness: bool = False, live: bool = True, package_spec: str = UVX_PACKAGE_SPEC
) -> str:
    """Return a stable uvx command for the packaged bridge runner."""

    mode = "harness" if harness else ("live" if live else "auto")
    return uvx_command(
        "python",
        "-m",
        "fl_mcp.bridge.runner",
        "--mode",
        mode,
        package_spec=package_spec,
    )


def uvx_selected_controller_command(*, package_spec: str = UVX_PACKAGE_SPEC) -> str:
    """Return a stable uvx command for the selected-controller bridge."""

    return uvx_command(
        "python",
        "-m",
        "fl_mcp.bridge.selected_controller_client",
        package_spec=package_spec,
    )


def _controller_script_candidates() -> tuple[Path, ...]:
    module_path = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in module_path.parents:
        candidates.append(parent / CONTROLLER_SCRIPT_RELATIVE_PATH)
    return tuple(dict.fromkeys(candidates))


def controller_script_path() -> Path:
    """Return the bundled FL Studio MIDI script entrypoint path."""

    candidates = _controller_script_candidates()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _latest_startup_log_mtime(user_data_dir: Path) -> float | None:
    startup_log_dir = user_data_dir / "Support/Logs/Startup"
    if not startup_log_dir.exists():
        return None
    mtimes = [path.stat().st_mtime for path in startup_log_dir.glob("Startup *.log")]
    return max(mtimes) if mtimes else None


def _active_user_data_dir(home: Path) -> Path:
    candidates = [home / relative_path for relative_path in _FL_USER_DATA_RELATIVE_PATHS]
    with_startup_logs = [
        (mtime, candidate)
        for candidate in candidates
        if (mtime := _latest_startup_log_mtime(candidate)) is not None
    ]
    if with_startup_logs:
        return max(with_startup_logs, key=lambda item: item[0])[1]

    for candidate in candidates:
        if (candidate / "Settings/Hardware").exists():
            return candidate

    return candidates[0]


def default_hardware_script_dir() -> Path:
    """Return the default FL Studio custom hardware script directory for this user."""

    return _active_user_data_dir(Path.home()) / "Settings/Hardware/FL MCP Bridge"


def default_file_bridge_dir() -> Path:
    """Return the FL-writable host-file bridge directory for the bundled script."""

    return default_hardware_script_dir() / "bridge"


def default_selected_controller_dir() -> Path:
    """Return the active FLStudioMCP selected-controller command directory."""

    return _active_user_data_dir(Path.home()) / "Settings/Hardware/FLStudioMCP"


def bridge_runner_descriptor() -> BridgeRunnerModeResponse:
    """Return the public descriptor used by install and doctor output."""
    controller_script = controller_script_path()
    controller_script_exists = controller_script.exists()
    return BridgeRunnerModeResponse(
        command=file_bridge_command(),
        harness_command=bridge_runner_command(harness=True),
        direct_command=bridge_runner_command(harness=False, live=True),
        selected_controller_command=selected_controller_command(),
        uvx_command=uvx_file_bridge_command(),
        uvx_harness_command=uvx_bridge_runner_command(harness=True),
        uvx_direct_command=uvx_bridge_runner_command(harness=False, live=True),
        uvx_selected_controller_command=uvx_selected_controller_command(),
        bridge_dir=str(default_file_bridge_dir()),
        selected_controller_dir=str(default_selected_controller_dir()),
        controller_script=str(controller_script),
        hardware_script_dir=str(default_hardware_script_dir()),
        status="available" if controller_script_exists else "missing",
        details=(
            "Packaged bridge commands available. Use command as FL_MCP_FL_STUDIO_BRIDGE_CMD "
            "after installing and selecting the controller script in FL Studio; use the "
            "harness command for CI smoke validation or the selected-controller command when "
            "an existing FL Studio MCP Controller script is already selected."
            if controller_script_exists
            else "Packaged bridge commands are available, but the bundled controller script "
            "could not be found in the installed package or source tree."
        ),
    )


def run_harness_smoke() -> dict[str, object]:
    """Run read and mutation operations through the live subprocess boundary."""
    bridge = FLStudioBridge(mode="live", live_command=bridge_runner_command(harness=True))
    read_result = bridge.execute_operation(
        domain="transport",
        operation="get_state",
        payload={},
        provider="flapi-live",
    )
    mutation_result = bridge.execute_operation(
        domain="transport",
        operation="set_tempo",
        payload={"bpm": 120.0},
        provider="flapi-live",
    )
    return {
        "read": {
            "success": read_result.success,
            "error_code": read_result.error_code,
            "message": read_result.message,
        },
        "mutation": {
            "success": mutation_result.success,
            "error_code": mutation_result.error_code,
            "message": mutation_result.message,
        },
        "ok": read_result.success and mutation_result.success,
    }
