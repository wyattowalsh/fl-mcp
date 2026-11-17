"""Tests for the production-flow setup-check script."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_setup_check_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "fl-mcp-production-flow"
        / "scripts"
        / "setup-check.py"
    )
    spec = importlib.util.spec_from_file_location("setup_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_check_ok_fails_on_json_error_health_despite_zero_returncode() -> None:
    setup_check = _load_setup_check_module()

    assert setup_check.doctor_check_ok(
        {
            "returncode": 0,
            "stdout": '{"health": "error", "checks": []}',
            "timed_out": False,
        }
    ) is False


def test_doctor_check_ok_passes_warning_with_zero_returncode() -> None:
    setup_check = _load_setup_check_module()

    assert setup_check.doctor_check_ok(
        {
            "returncode": 0,
            "stdout": '{"health": "warning", "checks": []}',
            "timed_out": False,
        }
    ) is True


def test_installed_controller_ready_requires_target_file_and_bridge_dir(tmp_path: Path) -> None:
    setup_check = _load_setup_check_module()
    target = tmp_path / "device_FL_MCP_Bridge.py"
    bridge = tmp_path / "bridge"
    target.write_text("script", encoding="utf-8")
    bridge.mkdir()
    ready, details = setup_check.installed_controller_ready(
        {
            "stdout": json.dumps(
                {
                    "fl_studio_controller": {"target_file": str(target)},
                    "bridge": {"bridge_dir": str(bridge)},
                }
            )
        }
    )
    assert ready is True
    assert details["target_ok"] is True
    assert details["bridge_ok"] is True

    missing, missing_details = setup_check.installed_controller_ready(
        {
            "stdout": json.dumps(
                {
                    "fl_studio_controller": {"target_file": str(tmp_path / "missing.py")},
                    "bridge": {"bridge_dir": str(bridge)},
                }
            )
        }
    )
    assert missing is False
    assert missing_details["target_ok"] is False
    assert missing_details["bridge_ok"] is True
    assert any("controller script" in step for step in missing_details["missing_steps"])


def test_missing_bridge_directory_blocks_live_readiness(tmp_path: Path) -> None:
    setup_check = _load_setup_check_module()
    target = tmp_path / "device_FL_MCP_Bridge.py"
    target.write_text("script", encoding="utf-8")
    bridge_file = tmp_path / "bridge"
    bridge_file.write_text("not a directory", encoding="utf-8")

    assert setup_check.doctor_check_ok(
        {
            "returncode": 0,
            "stdout": '{"health": "warning", "checks": []}',
            "timed_out": False,
        }
    ) is True

    ready, details = setup_check.installed_controller_ready(
        {
            "stdout": json.dumps(
                {
                    "fl_studio_controller": {"target_file": str(target)},
                    "environment": {"FL_MCP_FL_STUDIO_BRIDGE_DIR": str(bridge_file)},
                    "bridge": {"bridge_dir": str(tmp_path / "other-bridge")},
                }
            )
        }
    )
    assert ready is False
    assert details["target_ok"] is True
    assert details["bridge_ok"] is False
    assert any("bridge directory" in step for step in details["missing_steps"])


def test_doctor_check_ok_fails_when_fail_on_warning_exit_code() -> None:
    setup_check = _load_setup_check_module()

    assert setup_check.doctor_check_ok(
        {
            "returncode": 1,
            "stdout": '{"health": "warning", "checks": []}',
            "timed_out": False,
        }
    ) is False