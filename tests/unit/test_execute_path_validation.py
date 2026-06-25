"""Unit tests for execute-time local path validation (RV-001)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from fl_mcp.schemas.fl_tools import (
    AudioAnalyzeRequest,
    ChannelLoadSampleRequest,
    ProjectPathRequest,
)
from fl_mcp.tools import compact
from fl_mcp.util.paths import LocalPathValidationError, validate_operation_local_paths


def test_validate_operation_local_paths_skips_uri_paths() -> None:
    validate_operation_local_paths(
        "channels.load_sample",
        ChannelLoadSampleRequest(channel_index=0, file_path="mock://sample.wav"),
    )


def test_validate_operation_local_paths_rejects_outside_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.wav"
    outside.write_text("audio", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_operation_local_paths(
            "channels.load_sample",
            ChannelLoadSampleRequest(channel_index=0, file_path=str(outside)),
        )


def test_fl_execute_rejects_channels_load_sample_path_outside_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.wav"
    outside.write_text("audio", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    executed = compact.fl_execute(
        "channels.load_sample",
        {"channel_index": 0, "file_path": str(outside)},
        provider="mock",
    )

    assert executed["status"] == "error"
    assert executed["error"] == "Path is outside allowed inventory roots."
    result = cast(dict[str, object], executed["result"])
    assert result["error_code"] == "validation_failed"
    assert "outside allowed inventory roots" in cast(str, result["message"])


def test_fl_execute_allows_channels_load_sample_mock_uri() -> None:
    executed = compact.fl_execute(
        "channels.load_sample",
        {"channel_index": 0, "file_path": "mock://sample.wav"},
        provider="mock",
    )

    assert executed["status"] == "ok"


def test_fl_execute_skips_optional_render_export_path_when_omitted() -> None:
    executed = compact.fl_execute(
        "render.export",
        {"format": "wav"},
        provider="mock",
    )

    assert executed["status"] == "ok"


def test_fl_execute_validates_render_export_output_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "render.wav"
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    executed = compact.fl_execute(
        "render.export",
        {"format": "wav", "output_path": str(outside)},
        provider="mock",
    )

    assert executed["status"] == "error"
    assert "outside allowed inventory roots" in cast(str, executed["error"])


def test_validate_operation_local_paths_ignores_unknown_operation() -> None:
    validate_operation_local_paths(
        "transport.set_tempo",
        ProjectPathRequest(path=str(Path("/tmp/ignored.flp"))),
    )


def test_validate_operation_local_paths_optional_audio_analyze_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    validate_operation_local_paths(
        "audio.analyze",
        AudioAnalyzeRequest(analyzer="spectrum"),
    )

    outside = tmp_path / "outside.wav"
    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_operation_local_paths(
            "audio.analyze",
            AudioAnalyzeRequest(analyzer="spectrum", input_path=str(outside)),
        )


def test_validate_operation_local_paths_save_project_as_must_not_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = allowed / "new-project.flp"
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    validate_operation_local_paths(
        "general.save_project_as",
        ProjectPathRequest(path=str(target)),
    )

    outside = tmp_path / "escape.flp"
    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_operation_local_paths(
            "general.save_project_as",
            ProjectPathRequest(path=str(outside)),
        )


def test_fl_render_rejects_mock_provider_path_outside_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "render.wav"
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    rendered = compact.fl_render(
        {"output_path": str(outside), "provider": "mock"},
    )

    assert rendered["status"] == "error"
    assert "outside allowed inventory roots" in cast(str, rendered["error"])


def test_fl_analyze_audio_rejects_mock_provider_path_outside_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "analysis.wav"
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    analyzed = compact.fl_analyze_audio(
        {"input_path": str(outside), "provider": "mock"},
    )

    assert analyzed["status"] == "error"
    assert "outside allowed inventory roots" in cast(str, analyzed["error"])


def test_validate_operation_local_paths_rejects_preset_path_outside_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from fl_mcp.schemas.fl_tools import PluginProfilePresetRequest

    outside = tmp_path / "escape.fxp"
    outside.write_text("preset", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_operation_local_paths(
            "plugins.load_profile_preset",
            PluginProfilePresetRequest(
                profile_id="lennardigital.sylenth1",
                preset_path=str(outside),
                channel_index=0,
            ),
        )


def test_validate_operation_local_paths_open_project_must_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    project = allowed / "project.flp"
    project.write_text("flp", encoding="utf-8")
    monkeypatch.setattr(
        "fl_mcp.util.paths.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )

    validate_operation_local_paths(
        "general.open_project",
        ProjectPathRequest(path=str(project)),
    )

    missing = allowed / "missing.flp"
    with pytest.raises(LocalPathValidationError, match="does not exist"):
        validate_operation_local_paths(
            "general.open_project",
            ProjectPathRequest(path=str(missing)),
        )