"""Tests for uniform compact-surface error envelopes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest

from fl_mcp.server import factory as factory_module
from fl_mcp.tools import compact


def test_fl_render_returns_typed_error_for_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exploding_render(_request: object) -> dict[str, object]:
        msg = "render pipeline unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(compact.public, "render_project", exploding_render)

    result = compact.fl_render({})

    assert result["status"] == "error"
    assert result["tool"] == "fl_render"
    assert result["error"] == "render pipeline unavailable"


def test_fl_analyze_audio_returns_typed_error_for_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exploding_analyze(_request: object) -> dict[str, object]:
        msg = "analysis pipeline unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(compact.public, "analyze_audio", exploding_analyze)

    result = compact.fl_analyze_audio({})

    assert result["status"] == "error"
    assert result["tool"] == "fl_analyze_audio"
    assert result["error"] == "analysis pipeline unavailable"


def test_fl_browser_rejects_sample_path_outside_inventory_roots(
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

    result = compact.fl_browser(
        action="load",
        kind="sample",
        request={"file_path": str(outside), "channel_index": 0},
        provider="mock",
    )

    assert result["status"] == "error"
    assert "outside allowed inventory roots" in cast(str, result["error"])


def test_fl_browser_allows_mock_sample_uri() -> None:
    result = compact.fl_browser(
        action="load",
        kind="sample",
        request={"file_path": "mock://sample.wav", "channel_index": 0},
        provider="mock",
    )

    assert result["status"] == "ok"


def test_async_tool_handler_converts_unhandled_exceptions_to_error_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", None)

    def exploding_handler() -> dict[str, object]:
        msg = "synthetic compact tool failure"
        raise RuntimeError(msg)

    async_handler = factory_module._async_tool_handler("fl_render", exploding_handler)
    result = asyncio.run(async_handler())

    assert result["status"] == "error"
    assert result["tool"] == "fl_render"
    assert result["error"] == "synthetic compact tool failure"


def test_load_profile_preset_rejects_path_outside_inventory_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from fl_mcp.plugin_profiles.registry import get_plugin_profile_registry
    from fl_mcp.schemas.plugin_profiles import PluginInventoryItem

    outside = tmp_path / "escape.fxp"
    outside.write_text("preset", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(
        "fl_mcp.plugin_profiles.operations.inventory_scan_roots",
        lambda: (allowed.resolve(),),
    )
    registry = get_plugin_profile_registry()

    class InstalledRegistry:
        def profile(self, profile_or_plugin_id: str):
            return registry.profile(profile_or_plugin_id)

        def inventory_item(self, profile_id: str) -> PluginInventoryItem:
            return PluginInventoryItem(
                plugin_id=profile_id,
                display_name="Sylenth1",
                status="filesystem_only",
            )

    monkeypatch.setattr(
        "fl_mcp.plugin_profiles.operations.get_plugin_profile_registry",
        lambda: InstalledRegistry(),
    )

    executed = compact.fl_execute(
        "plugins.load_profile_preset",
        {
            "profile_id": "lennardigital.sylenth1",
            "preset_path": str(outside),
            "channel_index": 0,
        },
        provider="mock",
    )
    result = cast(dict[str, object], executed["result"])

    assert executed["status"] == "error"
    assert result["error_code"] == "validation_failed"
    assert "outside allowed inventory roots" in cast(str, result["message"])