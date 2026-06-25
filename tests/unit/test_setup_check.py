"""Tests for the production-flow setup-check script."""

from __future__ import annotations

import importlib.util
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


def test_doctor_check_ok_fails_when_fail_on_warning_exit_code() -> None:
    setup_check = _load_setup_check_module()

    assert setup_check.doctor_check_ok(
        {
            "returncode": 1,
            "stdout": '{"health": "warning", "checks": []}',
            "timed_out": False,
        }
    ) is False