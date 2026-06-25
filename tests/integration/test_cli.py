"""Integration tests for the fl-mcp CLI entry point."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fl_mcp.bridge.bundle import default_file_bridge_dir
from fl_mcp.cli import doctor as doctor_cli
from fl_mcp.cli.main import main
from fl_mcp.interfaces.status import DiagnosticCheck, HealthState

# ---------------------------------------------------------------------------
# Direct main() invocation tests (in-process, fast)
# ---------------------------------------------------------------------------


def test_doctor_runs() -> None:
    assert main(["doctor", "--format", "json"]) == 0


def test_doctor_table_format() -> None:
    """Doctor with default table format exits 0."""
    assert main(["doctor", "--format", "table"]) == 0


def test_doctor_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Doctor --format json emits valid, well-structured JSON."""
    rc = main(["doctor", "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # The payload must contain top-level keys from HelperStatusPayload
    assert "health" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)
    assert len(data["checks"]) > 0
    # Each check should have name, state, details
    for check in data["checks"]:
        assert "name" in check
        assert "state" in check
    check_names = {check["name"] for check in data["checks"]}
    assert "controller-byte-match" in check_names
    assert "status-freshness" in check_names
    assert "host-poll-probe" in check_names


def test_doctor_returns_nonzero_when_health_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor exits 1 when aggregated health is ERROR."""

    def _error_checks() -> list[DiagnosticCheck]:
        return [
            DiagnosticCheck(
                name="controller-byte-match",
                state=HealthState.ERROR,
                details="installed controller missing",
            )
        ]

    monkeypatch.setattr(doctor_cli, "collect_bridge_checks", _error_checks)

    assert main(["doctor", "--format", "json"]) == 1
    assert main(["doctor", "--format", "table"]) == 1


def test_doctor_warning_exits_zero_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor exits 0 when aggregated health is WARNING unless --fail-on-warning."""

    def _warning_checks() -> list[DiagnosticCheck]:
        return [
            DiagnosticCheck(
                name="fl-process-probe",
                state=HealthState.WARNING,
                details="FL Studio process not detected",
            )
        ]

    monkeypatch.setattr(doctor_cli, "collect_bridge_checks", _warning_checks)

    assert main(["doctor", "--format", "json"]) == 0
    assert main(["doctor", "--format", "json", "--fail-on-warning"]) == 1


def test_config_shell_env(capsys: pytest.CaptureFixture[str]) -> None:
    """config shell --format env prints shell export lines."""
    rc = main(["config", "shell", "--format", "env"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "export FL_MCP_HOME=" in captured.out
    assert "export FL_MCP_TRANSPORT=" in captured.out


def test_config_shell_json(capsys: pytest.CaptureFixture[str]) -> None:
    """config shell --format json emits valid JSON with expected keys."""
    rc = main(["config", "shell", "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "FL_MCP_HOME" in data
    assert "FL_MCP_TRANSPORT" in data


def test_diagnostics_shell_status(capsys: pytest.CaptureFixture[str]) -> None:
    """diagnostics shell --endpoint status emits valid JSON payload."""
    rc = main(["diagnostics", "shell", "--endpoint", "status"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "endpoint" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_diagnostics_shell_diagnostics_endpoint(capsys: pytest.CaptureFixture[str]) -> None:
    """diagnostics shell --endpoint diagnostics uses the diagnostics endpoint."""
    rc = main(["diagnostics", "shell", "--endpoint", "diagnostics"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "endpoint" in data
    assert "diagnostics" in data["endpoint"]


def test_install_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    """install --dry-run exits 0 and reports dry_run=true."""
    rc = main(["install", "--dry-run"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["dry_run"] is True
    assert data["action"] == "install"
    assert data["status"] == "ready"
    assert data["environment"]["FL_MCP_BRIDGE_MODE"] == "live"
    assert "fl_mcp.bridge.host_client" in data["environment"]["FL_MCP_FL_STUDIO_BRIDGE_CMD"]
    assert data["environment"]["FL_MCP_FL_STUDIO_BRIDGE_DIR"] == str(default_file_bridge_dir())
    assert (
        data["environment"]["FL_MCP_FL_STUDIO_BRIDGE_DIR"]
        .replace("\\", "/")
        .endswith("Settings/Hardware/FL MCP Bridge/bridge")
    )
    assert (
        "fl_mcp.bridge.selected_controller_client"
        in data["selected_controller_environment"]["FL_MCP_FL_STUDIO_BRIDGE_CMD"]
    )
    assert data["uvx_server"]["stdio"] == "uvx fl-mcp server run --mode stdio"
    assert (
        data["uvx_environment"]["FL_MCP_FL_STUDIO_BRIDGE_CMD"]
        == "uvx --from fl-mcp python -m fl_mcp.bridge.host_client"
    )
    assert (
        data["uvx_harness_environment"]["FL_MCP_FL_STUDIO_BRIDGE_CMD"]
        == "uvx --from fl-mcp python -m fl_mcp.bridge.runner --mode harness"
    )
    assert data["fl_studio_controller"]["target_file"].endswith("device_FL_MCP_Bridge.py")


def test_install_sync_controller_dry_run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """install --sync-controller --dry-run reports sync plan without writing."""
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"

    from fl_mcp.bridge.controller_install import sync_controller_script

    monkeypatch.setattr(
        "fl_mcp.cli.install.sync_controller_script",
        lambda **kwargs: sync_controller_script(
            source=source,
            target_dir=target_dir,
            dry_run=kwargs.get("dry_run", False),
        ),
    )

    rc = main(["install", "--dry-run", "--sync-controller"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["sync_controller"]["status"] == "planned"
    assert data["sync_controller"]["dry_run"] is True
    assert not (target_dir / "device_FL_MCP_Bridge.py").exists()


# ---------------------------------------------------------------------------
# argparse error-path tests (missing/unknown subcommands)
# ---------------------------------------------------------------------------


def test_no_subcommand_exits_nonzero() -> None:
    """Invoking main with no arguments should exit non-zero (required subcommand)."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_unknown_subcommand_exits_nonzero() -> None:
    """An unrecognised subcommand causes argparse to exit non-zero."""
    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent"])
    assert exc_info.value.code != 0


def test_config_missing_subcommand_exits_nonzero() -> None:
    """'config' alone (without 'shell') should fail because config_command is required."""
    with pytest.raises(SystemExit) as exc_info:
        main(["config"])
    assert exc_info.value.code != 0


def test_diagnostics_missing_subcommand_exits_nonzero() -> None:
    """'diagnostics' alone should fail because diagnostics_command is required."""
    with pytest.raises(SystemExit) as exc_info:
        main(["diagnostics"])
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# Subprocess tests (exercise the real console_scripts entry point)
# ---------------------------------------------------------------------------


@pytest.fixture()
def uv_run() -> list[str]:
    """Base command list for running fl-mcp via uv."""
    return ["uv", "run", "fl-mcp"]


class TestSubprocess:
    """Tests that exercise the installed console_scripts entry point."""

    def test_help_flag(self, uv_run: list[str]) -> None:
        """fl-mcp --help exits 0 and contains usage information."""
        result = subprocess.run(
            [*uv_run, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "fl-mcp" in result.stdout.lower()

    def test_version_flag(self, uv_run: list[str]) -> None:
        """fl-mcp --version exits 0 and reports the package version."""
        result = subprocess.run(
            [*uv_run, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout.strip().startswith("fl-mcp ")

    def test_doctor_subprocess(self, uv_run: list[str]) -> None:
        """fl-mcp doctor --format json via subprocess exits 0 with valid JSON."""
        result = subprocess.run(
            [*uv_run, "doctor", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "health" in data

    def test_config_shell_subprocess(self, uv_run: list[str]) -> None:
        """fl-mcp config shell --format json via subprocess exits 0."""
        result = subprocess.run(
            [*uv_run, "config", "shell", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "FL_MCP_HOME" in data

    def test_diagnostics_shell_subprocess(self, uv_run: list[str]) -> None:
        """fl-mcp diagnostics shell via subprocess exits 0."""
        result = subprocess.run(
            [*uv_run, "diagnostics", "shell"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "checks" in data

    def test_unknown_subcommand_subprocess(self, uv_run: list[str]) -> None:
        """fl-mcp nonexistent via subprocess exits non-zero."""
        result = subprocess.run(
            [*uv_run, "nonexistent"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0

    def test_no_args_subprocess(self, uv_run: list[str]) -> None:
        """fl-mcp with no arguments via subprocess exits non-zero."""
        result = subprocess.run(
            uv_run,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
