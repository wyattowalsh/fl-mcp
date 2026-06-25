"""Tests for controller script install/sync helpers."""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

from fl_mcp.bridge.controller_install import sync_controller_script


def test_sync_controller_script_copies_and_verifies_byte_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled controller\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"

    result = sync_controller_script(dry_run=False, source=source, target_dir=target_dir)

    target_file = target_dir / "device_FL_MCP_Bridge.py"
    assert result.status == "synced"
    assert result.byte_match_verified is True
    assert target_file.is_file()
    assert filecmp.cmp(source, target_file, shallow=False)


def test_sync_controller_script_backs_up_existing_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled v2\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "device_FL_MCP_Bridge.py"
    target_file.write_text("# installed v1\n", encoding="utf-8")

    result = sync_controller_script(dry_run=False, source=source, target_dir=target_dir)

    assert result.status == "synced"
    assert result.backup_file is not None
    assert Path(result.backup_file).is_file()
    assert filecmp.cmp(source, target_file, shallow=False)


def test_sync_controller_script_dry_run_reports_plan_without_writing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"

    result = sync_controller_script(dry_run=True, source=source, target_dir=target_dir)

    assert result.status == "planned"
    assert not (target_dir / "device_FL_MCP_Bridge.py").exists()


def test_sync_controller_script_reports_unchanged_when_already_matching(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"
    target_dir.mkdir(parents=True)
    target = target_dir / "device_FL_MCP_Bridge.py"
    target.write_text("# bundled\n", encoding="utf-8")

    result = sync_controller_script(dry_run=False, source=source, target_dir=target_dir)

    assert result.status == "unchanged"
    assert result.byte_match_verified is True


def test_sync_controller_script_errors_when_bundled_source_missing(
    tmp_path: Path,
) -> None:
    missing_source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    target_dir = tmp_path / "hardware"

    result = sync_controller_script(
        dry_run=False,
        source=missing_source,
        target_dir=target_dir,
    )

    assert result.status == "error"
    assert result.error is not None
    assert "Bundled controller script missing" in result.error


def test_sync_controller_script_errors_when_post_copy_byte_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "bundle" / "device_FL_MCP_Bridge.py"
    source.parent.mkdir(parents=True)
    source.write_text("# bundled\n", encoding="utf-8")
    target_dir = tmp_path / "hardware"

    def _cmp_returns_false(_left: Path, _right: Path, *, shallow: bool = False) -> bool:
        return False

    monkeypatch.setattr(filecmp, "cmp", _cmp_returns_false)

    result = sync_controller_script(dry_run=False, source=source, target_dir=target_dir)

    assert result.status == "error"
    assert result.error is not None
    assert "does not byte-match" in result.error