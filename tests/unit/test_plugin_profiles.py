"""Unit tests for plugin-profile registry and mapped-control behavior."""

from __future__ import annotations

import pytest

from fl_mcp.plugin_profiles.registry import PluginProfileRegistry, normalize_control_value
from fl_mcp.plugin_profiles.seeds import seed_profiles
from fl_mcp.schemas.plugin_profiles import PluginCalibration, PluginControl, PluginValueMap
from fl_mcp.tools import compact


def test_seed_profiles_include_local_target_families() -> None:
    profiles = {profile.profile_id: profile for profile in seed_profiles()}

    assert "lennardigital.sylenth1" in profiles
    assert "fabfilter.pro_q3" in profiles
    assert "fabfilter.pro_c2" in profiles
    assert "xfer.serum2" in profiles
    assert "cableguys.shaperbox2" in profiles
    assert profiles["lennardigital.sylenth1"].support_priority == "P0_paid_installed"
    assert profiles["fabfilter.micro"].support_priority == "P1_paid_detected_or_suite"
    assert profiles["image_line.fruity_parametric_eq_2"].support_priority == (
        "P2_popular_useful_stock_or_free"
    )
    assert profiles["izotope.trash"].status == "desired"


def test_registry_resolves_aliases_and_calibration_indices() -> None:
    calibration = PluginCalibration(
        profile_id="lennardigital.sylenth1",
        format="vst3",
        mapped_controls={"filter.cutoff": 42},
        fingerprint="test-instance",
    )
    registry = PluginProfileRegistry(calibrations=[calibration])

    profile = registry.profile("Sylenth 1")
    resolved = registry.resolve_control(
        "Sylenth1",
        "filter.cutoff",
        plugin_format="vst3",
        fingerprint="test-instance",
    )

    assert profile is not None
    assert profile.profile_id == "lennardigital.sylenth1"
    assert resolved[0] is not None
    assert resolved[1] is not None
    assert resolved[2] == 42
    assert resolved[3] == calibration


def test_value_maps_convert_semantic_values_to_normalized_values() -> None:
    frequency = PluginControl(
        control_id="filter.cutoff",
        label="Filter Cutoff",
        value_map=PluginValueMap(kind="log_frequency", min_value=20, max_value=20000),
    )
    percent = PluginControl(
        control_id="mix",
        label="Mix",
        value_map=PluginValueMap(kind="percent"),
    )

    assert 0 < normalize_control_value(frequency, 1000) < 1
    assert normalize_control_value(percent, 50) == 0.5
    with pytest.raises(ValueError, match="out of range"):
        normalize_control_value(percent, 500)


def test_mapped_parameter_write_fails_closed_without_calibration() -> None:
    executed = compact.fl_execute(
        "plugins.set_mapped_parameter",
        {
            "profile_id": "lennardigital.sylenth1",
            "control_id": "filter.cutoff",
            "value": 1000.0,
        },
        provider="mock",
    )
    result = executed["result"]

    assert executed["status"] == "error"
    assert result["error_code"] == "calibration_required"
    assert "Run plugins.probe_instance" in result["result"]["remediation"]


def test_raw_parameter_enumeration_uses_mock_bridge() -> None:
    executed = compact.fl_execute(
        "plugins.enumerate_parameters",
        {"channel_index": 0, "max_parameters": 4},
        provider="mock",
    )
    result = executed["result"]
    parameters = result["result"]["parameters"]

    assert executed["status"] == "ok"
    assert result["status"] == "ok"
    assert result["result"]["parameter_count"] == 4
    assert parameters[0]["parameter_index"] == 0
    assert parameters[0]["parameter_name"] == "Cutoff"


def test_generate_raw_profile_returns_indexed_controls() -> None:
    executed = compact.fl_execute(
        "plugins.generate_raw_profile",
        {
            "profile_id": "lennardigital.sylenth1",
            "channel_index": 0,
            "max_parameters": 4,
        },
        provider="mock",
    )
    raw_profile = executed["result"]["result"]["raw_profile"]

    assert executed["status"] == "ok"
    assert raw_profile["support_state"] == "raw_enumerated"
    assert raw_profile["semantic_controls"][0]["parameter_index"] == 0
    assert raw_profile["semantic_controls"][0]["control_origin"] == "live_raw"


def test_priority_support_audit_includes_paid_targets() -> None:
    executed = compact.fl_execute(
        "plugins.priority_support_audit",
        {"include_p3": False, "fail_on_missing_priority": False},
        provider="mock",
    )
    result = executed["result"]["result"]

    assert executed["status"] == "ok"
    assert result["counts_by_priority"]["P0_paid_installed"] >= 1
    assert any(row["profile_id"] == "lennardigital.sylenth1" for row in result["rows"])


def test_write_calibration_overlay_can_validate_without_persistence() -> None:
    executed = compact.fl_execute(
        "plugins.write_calibration_overlay",
        {
            "profile_id": "lennardigital.sylenth1",
            "mapped_controls": {"filter.cutoff": 0},
            "plugin_format": "vst3",
            "fingerprint": "unit-test",
            "persist": False,
        },
        provider="mock",
    )
    result = executed["result"]["result"]

    assert executed["status"] == "ok"
    assert result["persistence"] == "not_written"
    assert result["calibration"]["mapped_controls"] == {"filter.cutoff": 0}
