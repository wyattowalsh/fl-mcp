"""Tests for the automation domain tools."""

from __future__ import annotations

import pytest

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE
from fl_mcp.graph.domains import DOMAINS
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS


def test_automation_domain_registered() -> None:
    assert "automation" in DOMAINS


def test_automation_tool_specs_count() -> None:
    automation_specs = [s for s in FL_TOOL_SPECS if s.domain == "automation"]
    assert len(automation_specs) == 7, (
        f"Expected 7 automation specs, got {len(automation_specs)}: "
        f"{[s.name for s in automation_specs]}"
    )


def test_automation_tool_names() -> None:
    automation_names = {s.name for s in FL_TOOL_SPECS if s.domain == "automation"}
    expected = {
        "automation_list_clips",
        "automation_get_clip",
        "automation_create_clip",
        "automation_delete_clip",
        "automation_write_points",
        "automation_read_points",
        "automation_link_to_parameter",
    }
    assert automation_names == expected


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("list_clips", {}),
        ("get_clip", {"clip_index": 0}),
        ("create_clip", {"name": "My Automation"}),
        ("delete_clip", {"clip_index": 0}),
        ("write_points", {"clip_index": 0, "points": [{"time": 0.0, "value": 0.5}]}),
        ("read_points", {"clip_index": 0}),
        (
            "link_to_parameter",
            {
                "clip_index": 0,
                "target_type": "mixer",
                "target_index": 1,
                "parameter_index": 0,
            },
        ),
    ],
)
def test_automation_mock_execution(operation: str, payload: dict) -> None:
    result = DEFAULT_BRIDGE.execute_operation(
        domain="automation",
        operation=operation,
        payload=payload,
    )
    assert result.success, f"automation.{operation} failed: {result.error_code} {result.message}"
    assert result.bridge_mode == "mock"


def test_automation_write_points_returns_count() -> None:
    points = [{"time": float(i), "value": i / 4.0} for i in range(4)]
    result = DEFAULT_BRIDGE.execute_operation(
        domain="automation",
        operation="write_points",
        payload={"clip_index": 0, "points": points},
    )
    assert result.success
    assert result.result["points_written"] == 4


def test_automation_read_points_returns_list() -> None:
    result = DEFAULT_BRIDGE.execute_operation(
        domain="automation",
        operation="read_points",
        payload={"clip_index": 0},
    )
    assert result.success
    assert isinstance(result.result["points"], list)
    assert len(result.result["points"]) > 0
