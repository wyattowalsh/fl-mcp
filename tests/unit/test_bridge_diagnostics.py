"""Tests for bridge doctor diagnostics."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from fl_mcp.bridge import bridge_diagnostics
from fl_mcp.bridge.bridge_diagnostics import (
    BridgeDiagnosticContext,
    check_controller_byte_match,
    check_fl_process,
    check_status_freshness,
    collect_bridge_checks,
)
from fl_mcp.interfaces.status import HealthState


def _ctx(tmp_path: Path) -> BridgeDiagnosticContext:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled\n", encoding="utf-8")
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    return BridgeDiagnosticContext(
        controller_source=source,
        controller_target=tmp_path / "hardware" / "device_FL_MCP_Bridge.py",
        bridge_dir=bridge_dir,
        harness_command="python -m fl_mcp.bridge.runner --mode harness",
        selected_controller_command="python -m fl_mcp.bridge.selected_controller_client",
        selected_controller_dir=str(tmp_path / "selected"),
    )


def test_check_controller_byte_match_warns_when_target_missing(tmp_path: Path) -> None:
    check = check_controller_byte_match(_ctx(tmp_path))

    assert check.name == "controller-byte-match"
    assert check.state is HealthState.WARNING
    assert "sync-controller" in check.details


def test_check_controller_byte_match_ok_when_files_match(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ctx.controller_target.parent.mkdir(parents=True)
    ctx.controller_target.write_text("# bundled\n", encoding="utf-8")

    check = check_controller_byte_match(ctx)

    assert check.state is HealthState.OK


def test_check_status_freshness_warns_on_stale_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _ctx(tmp_path)
    now = 2000.0
    monkeypatch.setattr(bridge_diagnostics.time, "time", lambda: now)
    (ctx.bridge_dir / "status.json").write_text(
        json.dumps({"updated_at": now - 120.0, "state": "ready"}),
        encoding="utf-8",
    )

    check = check_status_freshness(ctx)

    assert check.state is HealthState.WARNING
    assert "stale" in check.details


def test_check_status_freshness_ok_for_recent_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _ctx(tmp_path)
    now = 2000.0
    monkeypatch.setattr(bridge_diagnostics.time, "time", lambda: now)
    (ctx.bridge_dir / "status.json").write_text(
        json.dumps({"updated_at": now - 5.0, "state": "ready"}),
        encoding="utf-8",
    )

    check = check_status_freshness(ctx)

    assert check.state is HealthState.OK


def test_check_fl_process_skips_probe_off_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge_diagnostics.platform, "system", lambda: "Linux")

    check = check_fl_process()

    assert check.state is HealthState.OK
    assert "optional" in check.details


def test_collect_bridge_checks_includes_expected_names() -> None:
    names = {check.name for check in collect_bridge_checks()}

    assert names >= {
        "bundle",
        "bridge-harness",
        "controller-byte-match",
        "fl-studio-process",
        "status-freshness",
        "host-poll-probe",
        "controller-selection",
        "selected-controller-adapter",
    }