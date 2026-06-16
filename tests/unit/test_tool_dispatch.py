"""End-to-end dispatch tests for every FL tool handler through the operations module."""

from __future__ import annotations

import pytest

from fl_mcp.operations import (
    build_operation_tool_handlers,
    execute_operation_tool,
    list_operation_specs,
)
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS

# ---------------------------------------------------------------------------
# Minimal valid request payloads for tools whose request models have required
# fields.  Tools not listed here can be dispatched with ``request=None``
# (i.e. the request model has no mandatory fields).
# ---------------------------------------------------------------------------

_MINIMAL_REQUESTS: dict[str, dict[str, object]] = {
    # midi domain
    "midi_send_note": {"note": 60},
    "midi_send_cc": {"control": 1, "value": 64},
    "midi_send_program_change": {"program": 0},
    "midi_send_pitch_bend": {"value": 0},
    # transport domain
    "transport_set_tempo": {"bpm": 120.0},
    "transport_set_song_position": {"position_beats": 0.0},
    "transport_set_loop_mode": {"mode": "song"},
    "transport_set_playback_speed": {"speed": 1.0},
    # mixer domain
    "mixer_get_track": {"track_index": 0},
    "mixer_get_meter_level": {"track_index": 0},
    "mixer_update_track": {"track_index": 0},
    "mixer_set_stereo_separation": {"track_index": 0, "stereo_separation": 0.0},
    "mixer_get_track_color": {"track_index": 0},
    "mixer_get_track_volume": {"track_index": 0},
    "mixer_get_track_pan": {"track_index": 0},
    "mixer_is_track_armed": {"track_index": 0},
    # channels domain
    "channels_get_channel": {"channel_index": 0},
    "channels_get_target_fx_track": {"channel_index": 0},
    "channels_select_channel": {"channel_index": 0},
    "channels_update_channel": {"channel_index": 0},
    "channels_route_to_mixer": {"channel_index": 0, "mixer_track_index": 0},
    "channels_get_step_sequence": {"channel_index": 0},
    "channels_set_step_sequence": {"channel_index": 0},
    "channels_trigger_note": {"channel_index": 0, "note": 60},
    "channels_set_pitch": {"channel_index": 0, "pitch": 0.0},
    "channels_duplicate": {"channel_index": 0},
    "channels_get_color": {"channel_index": 0},
    "channels_get_volume": {"channel_index": 0},
    "channels_get_pan": {"channel_index": 0},
    "channels_get_type": {"channel_index": 0},
    "channels_get_midi_in_port": {"channel_index": 0},
    # patterns domain
    "patterns_select": {"pattern_index": 0},
    "patterns_create": {"name": "test"},
    "patterns_rename": {"pattern_index": 0, "name": "renamed"},
    "patterns_set_length": {"pattern_index": 0, "length_beats": 4.0},
    "patterns_get_color": {"pattern_index": 0},
    "patterns_is_default": {"pattern_index": 0},
    # playlist domain
    "playlist_get_track": {"track_index": 0},
    "playlist_update_track": {"track_index": 0, "name": "renamed"},
    "playlist_place_clip": {
        "source": "pattern-0",
        "start_beats": 0.0,
        "length_beats": 4.0,
    },
    "playlist_move_clip": {
        "destination_track_index": 0,
        "destination_start_beats": 0.0,
    },
    "playlist_create_marker": {"name": "marker", "position_beats": 0.0},
    "playlist_get_track_color": {"track_index": 0},
    "playlist_get_track_activity": {"track_index": 0},
    # piano-roll domain
    "piano_roll_transpose": {"semitones": 0},
    # plugins domain
    "plugins_list": {"channel_index": 0},
    "plugins_get_parameters": {"channel_index": 0},
    "plugins_get_parameter": {"channel_index": 0, "parameter": "volume"},
    "plugins_set_parameter": {
        "channel_index": 0,
        "parameter": "volume",
        "value": 0.5,
    },
    "plugins_next_preset": {"channel_index": 0},
    "plugins_is_valid": {"channel_index": 0},
    "plugins_get_name": {"channel_index": 0},
    "plugins_get_parameter_count": {"channel_index": 0},
    "plugins_get_parameter_name": {"channel_index": 0, "parameter_index": 0},
    "plugins_get_preset_count": {"channel_index": 0},
    "plugins_show_window": {"channel_index": 0},
    "plugins_load": {"channel_index": 0, "plugin_name": "TestPlugin"},
    "plugins_replace": {"channel_index": 0, "plugin_name": "TestPlugin"},
    "plugins_prev_preset": {"channel_index": 0},
    # ui domain
    "ui_show_window": {"window": "mixer"},
    "ui_get_visibility": {"window": "mixer"},
    "ui_hide_window": {"window": "mixer"},
    # general domain
    "general_open_project": {"path": "/tmp/test.flp"},
    "general_save_project_as": {"path": "/tmp/test.flp"},
    # render domain
    "render_get_job": {"job_id": "test-job-0"},
    "render_cancel_job": {"job_id": "test-job-0"},
    # audio domain
    "audio_get_analysis": {"analysis_id": "test-analysis-0"},
    "audio_cancel_analysis": {"analysis_id": "test-analysis-0"},
    # mixer FX slot domain
    "mixer_get_slot_count": {"track_index": 0},
    "mixer_get_slot_name": {"track_index": 0, "slot_index": 0},
    "mixer_is_slot_enabled": {"track_index": 0, "slot_index": 0},
    "mixer_enable_slot": {"track_index": 0, "slot_index": 0, "enabled": True},
    "mixer_get_slot_plugin": {"track_index": 0, "slot_index": 0},
    "mixer_set_slot_plugin": {"track_index": 0, "slot_index": 0, "plugin_name": "TestPlugin"},
    # channels
    "channels_load_sample": {"channel_index": 0, "file_path": "/tmp/sample.wav"},
    # transport
    "transport_set_swing": {"value": 0.5},
    "transport_set_time_signature": {"numerator": 4, "denominator": 4},
    # plugins
    "plugins_get_preset_name": {"channel_index": 0, "preset_index": 0},
    "plugins_load_preset_by_name": {"channel_index": 0, "preset_name": "Default"},
    "plugins_inventory_scan": {"query": "sylenth", "include_paths": False},
    "plugins_list_profiles": {"query": "sylenth"},
    "plugins_get_profile": {"profile_id": "lennardigital.sylenth1"},
    "plugins_resolve_profile": {"query": "sylenth cutoff"},
    "plugins_probe_instance": {"profile_id": "lennardigital.sylenth1", "channel_index": 0},
    "plugins_enumerate_parameters": {"channel_index": 0, "max_parameters": 4},
    "plugins_probe_loadability": {"profile_id": "lennardigital.sylenth1", "channel_index": 0},
    "plugins_generate_raw_profile": {
        "profile_id": "lennardigital.sylenth1",
        "channel_index": 0,
        "max_parameters": 4,
    },
    "plugins_learn_parameter": {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
        "observed_parameter_index": 0,
    },
    "plugins_validate_profile": {"profile_id": "lennardigital.sylenth1"},
    "plugins_verify_profile_controls": {"profile_id": "lennardigital.sylenth1"},
    "plugins_write_calibration_overlay": {
        "profile_id": "lennardigital.sylenth1",
        "mapped_controls": {"filter.cutoff": 0},
        "persist": False,
    },
    "plugins_get_mapped_parameter": {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
    },
    "plugins_set_mapped_parameter": {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
        "value": 1000.0,
    },
    "plugins_load_profile_preset": {
        "profile_id": "lennardigital.sylenth1",
        "preset_name": "Default",
    },
    "plugins_list_local_presets": {"query": "sylenth", "include_paths": False},
    "plugins_reconcile_inventory": {"query": "sylenth", "include_paths": False},
    "plugins_priority_support_audit": {"include_p3": False, "fail_on_missing_priority": False},
    "plugins_export_support_matrix": {"include_p3": False},
    # automation domain
    "automation_get_clip": {"clip_index": 0},
    "automation_create_clip": {"name": "test"},
    "automation_delete_clip": {"clip_index": 0},
    "automation_write_points": {"clip_index": 0, "points": []},
    "automation_read_points": {"clip_index": 0},
    "automation_link_to_parameter": {
        "clip_index": 0,
        "target_type": "mixer",
        "target_index": 0,
        "parameter_index": 0,
    },
}


def _all_tool_names() -> list[str]:
    """Return sorted list of all FL tool names from the spec tuple."""
    return sorted(spec.name for spec in FL_TOOL_SPECS)


def _request_for(name: str) -> dict[str, object] | None:
    """Return a minimal valid request dict, or None if defaults suffice."""
    return _MINIMAL_REQUESTS.get(name)


# =====================================================================
# 1. Every tool can be dispatched without crashing
# =====================================================================


@pytest.mark.parametrize("tool_name", _all_tool_names())
def test_every_tool_dispatches_without_error(tool_name: str) -> None:
    """execute_operation_tool returns a dict for every registered FL tool."""
    result = execute_operation_tool(tool_name, _request_for(tool_name))
    assert isinstance(result, dict), f"{tool_name} did not return a dict"


# =====================================================================
# 2. All read-only tools return a dict with expected structure
# =====================================================================


def _read_tool_names() -> list[str]:
    return sorted(spec.name for spec in FL_TOOL_SPECS if spec.execution_mode == "read")


@pytest.mark.parametrize("tool_name", _read_tool_names())
def test_read_tools_return_status(tool_name: str) -> None:
    """Read-mode tools return a dict containing a 'status' key."""
    result = execute_operation_tool(tool_name, _request_for(tool_name))
    assert isinstance(result, dict)
    assert "status" in result, f"Read tool {tool_name} missing 'status' key"


# =====================================================================
# 3. All transaction tools return a dict with status
# =====================================================================


def _transaction_tool_names() -> list[str]:
    return sorted(spec.name for spec in FL_TOOL_SPECS if spec.execution_mode == "transaction")


@pytest.mark.parametrize("tool_name", _transaction_tool_names())
def test_transaction_tools_return_status(tool_name: str) -> None:
    """Transaction-mode tools return a dict containing a 'status' key."""
    result = execute_operation_tool(tool_name, _request_for(tool_name))
    assert isinstance(result, dict)
    assert "status" in result, f"Transaction tool {tool_name} missing 'status' key"


# =====================================================================
# 4. Domain grouping is correct — every tool name starts with its domain
# =====================================================================


_DOMAIN_PREFIXES: dict[str, str] = {
    "connection": "connection_",
    "midi": "midi_",
    "transport": "transport_",
    "mixer": "mixer_",
    "channels": "channels_",
    "patterns": "patterns_",
    "playlist": "playlist_",
    "piano-roll": "piano_roll_",
    "plugins": "plugins_",
    "ui": "ui_",
    "general": "general_",
    "render": "render_",
    "audio": "audio_",
    "device": "device_",
    "arrangement": "arrangement_",
    "automation": "automation_",
}


def test_domain_grouping_is_correct() -> None:
    """Every tool name is prefixed by a canonical form of its domain."""
    for spec in FL_TOOL_SPECS:
        expected_prefix = _DOMAIN_PREFIXES.get(spec.domain)
        assert expected_prefix is not None, f"No prefix mapping for domain '{spec.domain}'"
        assert spec.name.startswith(expected_prefix), (
            f"Tool '{spec.name}' in domain '{spec.domain}' does not start with '{expected_prefix}'"
        )


# =====================================================================
# 5. Handler names match spec names
# =====================================================================


def test_handler_names_match_spec_names() -> None:
    """build_operation_tool_handlers() keys are exactly the set of spec names."""
    handler_names = set(build_operation_tool_handlers())
    spec_names = {spec.name for spec in FL_TOOL_SPECS}
    assert handler_names == spec_names


# =====================================================================
# 6. No duplicate tool names
# =====================================================================


def test_no_duplicate_tool_names() -> None:
    """All FL_TOOL_SPECS names are unique."""
    names = [spec.name for spec in FL_TOOL_SPECS]
    assert len(names) == len(set(names)), (
        f"Duplicate tool names found: {sorted(n for n in names if names.count(n) > 1)}"
    )


def test_tool_count_matches_expected() -> None:
    """Guard-rail: the catalog contains exactly 216 tool specs."""
    assert len(FL_TOOL_SPECS) == 216


# =====================================================================
# 7. list_operation_specs round-trip consistency
# =====================================================================


def test_list_operation_specs_matches_fl_tool_specs() -> None:
    """list_operation_specs() returns one OperationSpec per FL_TOOL_SPECS entry."""
    ops = list_operation_specs()
    assert len(ops) == len(FL_TOOL_SPECS)
    op_names = {op.name for op in ops}
    spec_names = {spec.name for spec in FL_TOOL_SPECS}
    assert op_names == spec_names
