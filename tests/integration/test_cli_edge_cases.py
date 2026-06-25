"""Edge-case integration tests for CLI and server modules."""

from __future__ import annotations

import json

import pytest

from fl_mcp.bridge.bundle import default_file_bridge_dir
from fl_mcp.cli.main import main
from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import create_default_server, create_server

# ---------------------------------------------------------------------------
# CLI doctor command
# ---------------------------------------------------------------------------


class TestDoctorCommand:
    """Tests for `fl-mcp doctor` subcommand."""

    def test_doctor_json_returns_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["doctor", "--format", "json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "health" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_doctor_table_returns_table_formatted_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["doctor", "--format", "table"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "FL MCP Doctor" in captured.out
        assert "Health:" in captured.out

    def test_doctor_defaults_to_table_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["doctor"])
        assert rc == 0
        captured = capsys.readouterr()
        # Default format is table, so expect the table header
        assert "FL MCP Doctor" in captured.out
        assert "=============" in captured.out


# ---------------------------------------------------------------------------
# CLI config command
# ---------------------------------------------------------------------------


class TestConfigCommand:
    """Tests for `fl-mcp config shell` subcommand."""

    def test_config_shell_json_returns_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["config", "shell", "--format", "json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "FL_MCP_HOME" in data
        assert "FL_MCP_TRANSPORT" in data

    def test_config_shell_env_returns_env_style_exports(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["config", "shell", "--format", "env"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "export FL_MCP_HOME=" in captured.out
        assert "export FL_MCP_TRANSPORT=" in captured.out


# ---------------------------------------------------------------------------
# CLI diagnostics command
# ---------------------------------------------------------------------------


class TestDiagnosticsCommand:
    """Tests for `fl-mcp diagnostics shell` subcommand."""

    def test_diagnostics_shell_status_returns_json_payload(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["diagnostics", "shell", "--endpoint", "status"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "health" in data
        assert "endpoint" in data
        assert data["endpoint"] == "/v1/helper/status"


# ---------------------------------------------------------------------------
# CLI install command
# ---------------------------------------------------------------------------


class TestInstallCommand:
    """Tests for `fl-mcp install` subcommand."""

    def test_install_dry_run_completes_without_side_effects(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["install", "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["dry_run"] is True
        assert data["status"] == "ready"
        assert data["bridge"]["status"] == "available"
        assert "fl_mcp.bridge.host_client" in data["bridge"]["command"]
        assert "fl_mcp.bridge.runner" in data["bridge"]["harness_command"]
        assert (
            "fl_mcp.bridge.selected_controller_client"
            in data["bridge"]["selected_controller_command"]
        )
        assert data["bridge"]["uvx_command"] == (
            "uvx --from fl-mcp python -m fl_mcp.bridge.host_client"
        )
        assert data["uvx_server"]["stdio"] == "uvx fl-mcp server run --mode stdio"
        assert (
            data["uvx_environment"]["FL_MCP_FL_STUDIO_BRIDGE_CMD"] == data["bridge"]["uvx_command"]
        )
        assert data["bridge"]["bridge_dir"] == str(default_file_bridge_dir())
        assert (
            data["bridge"]["bridge_dir"]
            .replace("\\", "/")
            .endswith("Settings/Hardware/FL MCP Bridge/bridge")
        )


# ---------------------------------------------------------------------------
# CLI edge cases: no args, --help
# ---------------------------------------------------------------------------


class TestCLIEdgeCases:
    """Tests for bare invocation and help flag."""

    def test_no_args_raises_system_exit(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_help_flag_raises_system_exit_zero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_flag_raises_system_exit_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        assert capsys.readouterr().out.strip().startswith("fl-mcp ")


# ---------------------------------------------------------------------------
# Server dry-run surface contract
# ---------------------------------------------------------------------------


class TestServerRunDryRun:
    """Tests for compact server dry-run metadata."""

    def test_server_run_dry_run_reports_compact_surface(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["server", "run", "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["action"] == "server.run"
        assert data["runtime"]["surface"] == "compact"

    def test_server_run_dry_run_uses_settings_http_host_and_port(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fl_mcp.config.settings import settings

        monkeypatch.setattr(settings, "http_host", "127.0.0.2")
        monkeypatch.setattr(settings, "http_port", 9001)
        rc = main(["server", "run", "--mode", "http", "--dry-run"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["http"]["host"] == "127.0.0.2"
        assert data["http"]["port"] == 9001

    def test_http_requires_auth_token_in_all_environments(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fl_mcp.config.settings import settings

        monkeypatch.setattr(settings, "auth_token", None)
        monkeypatch.setattr(settings, "http_allow_unauthenticated", False)
        rc = main(["server", "run", "--mode", "http", "--environment", "production"])
        assert rc == 2
        assert "FL_MCP_AUTH_TOKEN is required for HTTP mode" in capsys.readouterr().out

        rc = main(["server", "run", "--mode", "http", "--environment", "dev"])
        assert rc == 2

    def test_production_http_dry_run_does_not_require_auth_token(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fl_mcp.config.settings import settings

        monkeypatch.setattr(settings, "auth_token", None)
        rc = main(
            [
                "server",
                "run",
                "--mode",
                "http",
                "--environment",
                "production",
                "--dry-run",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["runtime"]["environment"] == "production"


# ---------------------------------------------------------------------------
# Server factory functions
# ---------------------------------------------------------------------------


class TestServerFactory:
    """Tests for create_server and create_default_server factory functions."""

    def test_create_server_returns_server_instance(self) -> None:
        config = RuntimeConfig()
        server = create_server(config)
        assert server is not None
        assert hasattr(server, "name")

    def test_create_default_server_returns_server_instance(self) -> None:
        server = create_default_server()
        assert server is not None
        assert hasattr(server, "name")
