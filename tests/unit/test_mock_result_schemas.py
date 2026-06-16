"""Snapshot-style tests validating every mock handler returns a structurally
consistent result, grouped by domain.

Each domain defines expected key patterns for getters, setters, and actions.
Every entry in ``_MOCK_DISPATCH`` is exercised and the result is verified to:

1. Be a non-empty ``dict``.
2. Contain the expected keys for that domain pattern.
3. Have all values JSON-serializable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from fl_mcp.bridge.mock_generators import _MOCK_DISPATCH, mock_result

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call(domain: str, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke ``mock_result`` with a safe default payload."""
    return mock_result(domain, operation, payload or {}, rollback_class=None)


def _assert_base(result: dict[str, Any]) -> None:
    """Every result must be a non-empty dict with JSON-serializable values."""
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert len(result) > 0, "Result must be non-empty"
    # JSON round-trip proves all values are serializable
    serialized = json.dumps(result)
    assert isinstance(serialized, str)


def _assert_keys(result: dict[str, Any], required: set[str]) -> None:
    """Assert *required* keys are present in *result*."""
    missing = required - set(result.keys())
    assert not missing, f"Missing keys: {missing} in {set(result.keys())}"


# ---------------------------------------------------------------------------
# Domain operation registries
# ---------------------------------------------------------------------------

# Each entry: (operation, minimal_payload, required_keys_in_result)

_TRANSPORT_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("get_state", {}, {"playing", "recording", "bpm"}),
    ("get_playback_state", {}, {"playing", "recording", "bpm"}),
    ("get_tempo", {}, {"bpm"}),
    ("get_song_position", {}, {"position_beats"}),
    ("get_length", {}, {"length_beats", "mode"}),
    ("is_recording", {}, {"recording"}),
    ("get_song_pos_hint", {}, {"hint"}),
    # -- setters / actions --
    ("play", {}, {"acknowledged", "playing"}),
    ("pause", {}, {"acknowledged", "playing"}),
    ("stop", {}, {"acknowledged", "playing"}),
    ("record", {}, {"acknowledged", "playing", "recording"}),
    ("set_tempo", {"bpm": 140.0}, {"acknowledged", "bpm"}),
    ("set_song_position", {"position_beats": 4.0}, {"acknowledged", "position_beats"}),
    ("set_loop_mode", {"mode": "pattern"}, {"acknowledged", "loop_mode"}),
    ("set_playback_speed", {"speed": 1.5}, {"acknowledged", "playback_speed"}),
    ("rewind", {}, {"acknowledged", "rewinding"}),
    ("fast_forward", {}, {"acknowledged", "fast_forwarding"}),
    ("marker_jump", {"value": 1}, {"acknowledged", "jumped"}),
    # Time signature + swing (B5/C3)
    ("get_time_signature", {}, {"numerator", "denominator"}),
    (
        "set_time_signature",
        {"numerator": 4, "denominator": 4},
        {"acknowledged", "numerator", "denominator"},
    ),
    ("get_swing", {}, {"value", "swing_percent"}),
    ("set_swing", {"value": 0.5}, {"acknowledged", "value"}),
]

_MIXER_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("list_tracks", {}, {"tracks"}),
    ("get_track", {"track_index": 0}, {"track_index", "name", "volume"}),
    ("get_track_info", {"track_index": 0}, {"track_index", "name", "volume"}),
    ("get_track_count", {}, {"track_count"}),
    ("get_meter_level", {"track_index": 0}, {"track_index", "left", "right"}),
    ("get_track_color", {"index": 0}, {"color", "index"}),
    ("get_track_volume", {"index": 0}, {"volume", "index"}),
    ("get_track_pan", {"index": 0}, {"pan", "index"}),
    ("is_track_armed", {"index": 0}, {"armed", "index"}),
    ("get_route_send_level", {"index": 0, "dest_index": 0}, {"level", "index", "dest_index"}),
    ("get_eq_gain", {"index": 0, "band": 0}, {"value", "index", "band"}),
    ("get_eq_frequency", {"index": 0, "band": 0}, {"value", "index", "band"}),
    ("get_eq_bandwidth", {"index": 0, "band": 0}, {"value", "index", "band"}),
    # -- setters / actions --
    ("update_track", {"track_index": 0}, {"acknowledged", "track"}),
    ("set_stereo_separation", {"track_index": 0}, {"acknowledged", "track_index"}),
    ("set_volume", {"track_index": 0, "volume": 0.5}, {"acknowledged", "track_index"}),
    ("set_pan", {"track_index": 0, "pan": 0.0}, {"acknowledged", "track_index"}),
    ("mute", {"track_index": 0}, {"acknowledged", "track_index"}),
    ("solo", {"track_index": 0}, {"acknowledged", "track_index"}),
    ("set_name", {"track_index": 0, "name": "Test"}, {"acknowledged", "track_index"}),
    ("set_track_color", {"index": 0, "color": 0}, {"acknowledged", "color", "index"}),
    ("set_track_volume", {"index": 0, "volume": 0.5}, {"acknowledged", "volume", "index"}),
    ("set_track_pan", {"index": 0, "pan": 0.0}, {"acknowledged", "pan", "index"}),
    ("mute_track", {"index": 0}, {"acknowledged", "index", "muted"}),
    ("solo_track", {"index": 0}, {"acknowledged", "index", "solo"}),
    ("arm_track", {"index": 0}, {"acknowledged", "index", "armed"}),
    ("set_route_to", {"index": 0, "dest_index": 0}, {"acknowledged", "index", "dest_index"}),
    (
        "set_route_send_level",
        {"index": 0, "dest_index": 0, "level": 0.8},
        {"acknowledged", "index", "dest_index", "level"},
    ),
    (
        "set_eq_gain",
        {"index": 0, "band": 0, "value": 0.0},
        {"acknowledged", "index", "band", "value"},
    ),
    (
        "set_eq_frequency",
        {"index": 0, "band": 0, "value": 1000.0},
        {"acknowledged", "index", "band", "value"},
    ),
    # FX slot management (B2)
    ("get_slot_count", {"track_index": 0}, {"track_index", "slot_count"}),
    ("get_slot_name", {"track_index": 0, "slot_index": 0}, {"track_index", "slot_index", "name"}),
    (
        "is_slot_enabled",
        {"track_index": 0, "slot_index": 0},
        {"track_index", "slot_index", "enabled"},
    ),
    (
        "enable_slot",
        {"track_index": 0, "slot_index": 0, "enabled": True},
        {"acknowledged", "track_index", "slot_index"},
    ),
    (
        "get_slot_plugin",
        {"track_index": 0, "slot_index": 0},
        {"track_index", "slot_index", "plugin_name"},
    ),
    (
        "set_slot_plugin",
        {"track_index": 0, "slot_index": 0, "plugin_name": "Reverb"},
        {"acknowledged", "track_index", "slot_index"},
    ),
]

_CHANNELS_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("list_channels", {}, {"channels"}),
    ("list", {}, {"channels"}),
    ("get_channel", {"channel_index": 0}, {"channel_index", "name", "volume"}),
    ("get_info", {"channel_index": 0}, {"channel_index", "name", "volume"}),
    ("get_selected", {}, {"channel_index", "name", "selected"}),
    ("get_target_fx_track", {"channel_index": 0}, {"channel_index", "mixer_track_index"}),
    ("get_step_sequence", {"channel_index": 0}, {"channel_index", "steps"}),
    ("get_color", {"index": 0}, {"color", "index"}),
    ("get_volume", {"index": 0}, {"volume", "index"}),
    ("get_pan", {"index": 0}, {"pan", "index"}),
    ("get_type", {"index": 0}, {"type", "type_name", "index"}),
    ("get_midi_in_port", {"index": 0}, {"midi_in_port", "index"}),
    ("get_grid_bit", {"index": 0, "position": 0}, {"value", "index", "position"}),
    # -- setters / actions --
    ("select_channel", {"channel_index": 0}, {"acknowledged", "channel_index", "selected"}),
    ("update_channel", {"channel_index": 0}, {"acknowledged", "channel"}),
    ("set_volume", {"index": 0, "volume": 0.5}, {"acknowledged", "volume", "index"}),
    ("set_pan", {"index": 0, "pan": 0.0}, {"acknowledged", "pan", "index"}),
    ("mute", {"index": 0}, {"acknowledged", "index", "muted"}),
    ("solo", {"index": 0}, {"acknowledged", "index", "solo"}),
    (
        "route_to_mixer",
        {"channel_index": 0, "mixer_track_index": 1},
        {"acknowledged", "channel_index", "mixer_track_index"},
    ),
    (
        "set_step_sequence",
        {"channel_index": 0, "steps": [0, 4]},
        {"acknowledged", "channel_index", "steps"},
    ),
    ("trigger_note", {"channel_index": 0, "note": 60}, {"acknowledged", "queued", "channel_index"}),
    ("set_pitch", {"channel_index": 0, "pitch": 0.5}, {"acknowledged", "channel_index", "pitch"}),
    (
        "duplicate",
        {"channel_index": 0},
        {"acknowledged", "source_channel_index", "duplicated_channel_index"},
    ),
    ("set_color", {"index": 0, "color": 0}, {"acknowledged", "color", "index"}),
    (
        "set_grid_bit",
        {"index": 0, "position": 0, "value": True},
        {"acknowledged", "index", "position", "value"},
    ),
    ("quick_quantize", {"index": 0}, {"acknowledged", "index"}),
    # Sample loading (B3)
    (
        "load_sample",
        {"channel_index": 0, "file_path": "/tmp/kick.wav"},
        {"acknowledged", "channel_index", "loaded"},
    ),
]

_PATTERNS_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("list_patterns", {}, {"patterns"}),
    ("list", {}, {"patterns"}),
    ("get_color", {"index": 0}, {"color", "index"}),
    ("is_default", {"index": 0}, {"is_default", "index"}),
    # -- setters / actions --
    ("select_pattern", {"pattern_index": 1}, {"acknowledged", "pattern_index", "selected"}),
    ("select", {"pattern_index": 1}, {"acknowledged", "pattern_index", "selected"}),
    ("create_pattern", {"name": "New"}, {"acknowledged", "pattern"}),
    ("create", {"name": "New"}, {"acknowledged", "pattern"}),
    ("rename_pattern", {"pattern_index": 1, "name": "Renamed"}, {"acknowledged", "pattern"}),
    ("rename", {"pattern_index": 1, "name": "Renamed"}, {"acknowledged", "pattern"}),
    ("set_length", {"pattern_index": 1, "length": 32}, {"acknowledged", "updated_fields"}),
    ("set_color", {"index": 0, "color": 0}, {"acknowledged", "index", "color"}),
    ("clone", {"index": 1}, {"acknowledged", "source_index", "cloned_pattern_index"}),
    ("jump_to", {"index": 1}, {"acknowledged", "index", "jumped"}),
]

_PLAYLIST_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("list_tracks", {}, {"tracks"}),
    ("get_track", {"track_index": 1}, {"track_index", "name"}),
    ("get_track_info", {"track_index": 1}, {"track_index", "name"}),
    ("get_track_color", {"index": 1}, {"color", "index"}),
    ("get_track_activity", {"index": 1}, {"activity", "index"}),
    # -- setters / actions --
    ("update_track", {"track_index": 1}, {"acknowledged", "track"}),
    ("set_track_name", {"track_index": 1, "name": "Test"}, {"acknowledged", "track"}),
    ("set_track_color", {"index": 1, "color": 0}, {"acknowledged", "color", "index"}),
    ("mute_track", {"index": 1}, {"acknowledged", "index", "muted"}),
    ("solo_track", {"index": 1}, {"acknowledged", "index", "solo"}),
    ("select_track", {"index": 1}, {"acknowledged", "index", "selected"}),
    # Clip/marker management (C1)
    ("get_arrangement", {}, {"track_count", "clip_count"}),
    ("list_clips", {}, {"clips"}),
    (
        "place_clip",
        {"source": "pattern-0", "start_beats": 0.0, "length_beats": 4.0},
        {"acknowledged", "track_index", "position"},
    ),
    (
        "move_clip",
        {"destination_track_index": 0, "destination_start_beats": 0.0},
        {"acknowledged", "new_position"},
    ),
    ("delete_clip", {}, {"acknowledged", "deleted"}),
    ("list_markers", {}, {"markers"}),
    (
        "create_marker",
        {"name": "Intro", "position_beats": 0.0},
        {"acknowledged", "marker_index", "position"},
    ),
    ("update_marker", {}, {"acknowledged", "marker_index"}),
    ("delete_marker", {}, {"acknowledged", "deleted"}),
]

_CONNECTION_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("status", {}, {"connected", "mode"}),
    ("connect", {}, {"acknowledged", "connected"}),
]

_MIDI_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("list_ports", {}, {"inputs", "outputs"}),
    ("send_note", {"note": 60}, {"acknowledged", "queued", "message_type"}),
    ("send_cc", {"control": 1, "value": 64}, {"acknowledged", "queued", "message_type"}),
    ("send_program_change", {"program": 5}, {"acknowledged", "queued", "message_type"}),
    ("send_pitch_bend", {"value": 8192}, {"acknowledged", "queued", "message_type"}),
]

_PIANO_ROLL_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("get_state", {}, {"ppq", "notes"}),
    ("send_notes", {"notes": [{"note": 60}]}, {"acknowledged", "note_count", "notes"}),
    ("delete_notes", {"notes": [{"note": 60}]}, {"acknowledged", "deleted_count", "notes"}),
    ("clear", {}, {"acknowledged", "cleared"}),
    # AI generation ops (A4)
    ("quantize", {}, {"acknowledged", "notes_quantized"}),
    ("transpose", {"semitones": 2}, {"acknowledged", "semitones"}),
    ("humanize", {}, {"acknowledged", "variance"}),
    ("generate_chords", {}, {"acknowledged", "notes"}),
    ("generate_melody", {}, {"acknowledged", "notes"}),
    ("generate_bass", {}, {"acknowledged", "notes"}),
]

_PLUGINS_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("list_plugins", {"channel_index": 0}, {"plugins"}),
    ("list_params", {}, {"parameters"}),
    ("get_parameters", {}, {"parameters"}),
    ("get_parameter", {"parameter": "cutoff"}, {"parameter", "value"}),
    ("get_param_value", {"parameter": "cutoff"}, {"parameter", "value"}),
    (
        "set_parameter",
        {"parameter": "cutoff", "value": 0.7},
        {"acknowledged", "parameter", "value"},
    ),
    (
        "set_param_value",
        {"parameter": "cutoff", "value": 0.7},
        {"acknowledged", "parameter", "value"},
    ),
    ("next_preset", {}, {"acknowledged", "preset_direction"}),
    ("prev_preset", {}, {"acknowledged", "preset_direction"}),
    ("previous_preset", {}, {"acknowledged", "preset_direction"}),
    ("get_param_value_string", {"param_index": 0}, {"value_string", "param_index"}),
    ("get_color", {"index": 0}, {"color", "index"}),
    ("get_pad_info", {"chan_index": 0}, {"pad_info", "chan_index", "slot_index"}),
    # New plugin ops (from spec catalog)
    ("is_valid", {"channel_index": 0}, {"is_valid"}),
    ("get_name", {"channel_index": 0}, {"name"}),
    ("get_parameter_count", {"channel_index": 0}, {"parameter_count"}),
    ("get_parameter_name", {"channel_index": 0, "parameter_index": 0}, {"parameter_name"}),
    ("get_preset_count", {"channel_index": 0}, {"preset_count"}),
    ("show_window", {"channel_index": 0}, {"acknowledged", "visible"}),
    ("load", {"channel_index": 0, "plugin_name": "TestPlugin"}, {"acknowledged", "loaded"}),
    ("replace", {"channel_index": 0, "plugin_name": "TestPlugin"}, {"acknowledged", "replaced"}),
    ("get_preset_name", {"channel_index": 0, "preset_index": 0}, {"preset_name"}),
    (
        "load_preset_by_name",
        {"channel_index": 0, "preset_name": "Default"},
        {"acknowledged", "loaded"},
    ),
    ("inventory_scan", {}, {"inventory", "profiles", "presets"}),
    ("list_profiles", {}, {"profiles", "count"}),
    ("get_profile", {"profile_id": "lennardigital.sylenth1"}, {"profile_id", "profile"}),
    ("resolve_profile", {"query": "sylenth"}, {"query", "matches"}),
    ("probe_instance", {"channel_index": 0}, {"is_valid", "name", "parameter_count"}),
    (
        "enumerate_parameters",
        {"channel_index": 0},
        {"plugin_name", "parameter_count", "parameters"},
    ),
    ("probe_loadability", {"channel_index": 0}, {"support_state", "parameter_count"}),
    ("generate_raw_profile", {"channel_index": 0}, {"raw_profile", "persistence"}),
    (
        "learn_parameter",
        {"profile_id": "lennardigital.sylenth1", "control_id": "filter.cutoff"},
        {"profile_id", "control_id", "calibration"},
    ),
    (
        "validate_profile",
        {"profile_id": "lennardigital.sylenth1"},
        {"profile_id", "ready_for_mapped_execution", "failure_code"},
    ),
    (
        "verify_profile_controls",
        {"profile_id": "lennardigital.sylenth1"},
        {"profile_id", "verified_controls", "failures"},
    ),
    (
        "write_calibration_overlay",
        {"profile_id": "lennardigital.sylenth1", "mapped_controls": {"filter.cutoff": 0}},
        {"profile_id", "calibration", "persistence"},
    ),
    (
        "get_mapped_parameter",
        {"profile_id": "lennardigital.sylenth1", "control_id": "filter.cutoff"},
        {"profile_id", "control_id", "parameter_index", "value"},
    ),
    (
        "set_mapped_parameter",
        {"profile_id": "lennardigital.sylenth1", "control_id": "filter.cutoff", "value": 0.5},
        {"acknowledged", "profile_id", "control_id", "parameter_index", "value"},
    ),
    (
        "load_profile_preset",
        {"profile_id": "lennardigital.sylenth1", "preset_name": "Default"},
        {"acknowledged", "profile_id", "preset_name", "loaded"},
    ),
    ("list_local_presets", {}, {"presets", "count"}),
    ("reconcile_inventory", {}, {"by_status", "counts"}),
    ("priority_support_audit", {}, {"counts_by_priority", "rows", "blocking_count"}),
    ("export_support_matrix", {}, {"rows", "count"}),
]

_UI_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    # -- getters --
    ("get_visibility", {"window": "mixer"}, {"window", "visible"}),
    ("get_visible", {"window": "mixer"}, {"window", "visible"}),
    ("get_focused", {"index": 0}, {"index", "focused"}),
    ("get_focused_form_caption", {}, {"caption"}),
    ("get_focused_plugin_name", {}, {"plugin_name"}),
    ("get_snap_mode", {}, {"snap_mode"}),
    ("get_hint_msg", {}, {"hint_msg"}),
    ("get_step_edit_mode", {}, {"step_edit_mode"}),
    # -- setters / actions --
    ("show_window", {"window": "mixer"}, {"acknowledged", "window", "visible"}),
    ("hide_window", {"window": "mixer"}, {"acknowledged", "window", "visible"}),
    ("set_focused", {"index": 0}, {"acknowledged", "index", "focused"}),
    ("scroll_window", {"index": 0, "value": 10}, {"acknowledged", "index", "value"}),
    ("next_window", {}, {"acknowledged", "switched"}),
    ("set_snap_mode", {"value": 3}, {"acknowledged", "snap_mode"}),
    ("set_hint_msg", {"msg": "hello"}, {"acknowledged", "msg"}),
]

_GENERAL_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("get_version", {}, {"version", "build"}),
    ("get_project_title", {}, {"title"}),
    ("get_changed_flag", {}, {"changed"}),
    ("get_rec_ppq", {}, {"ppq"}),
    ("get_metronome", {}, {"metronome"}),
    ("get_precount", {}, {"precount"}),
    ("get_undo_history_pos", {}, {"position"}),
    ("get_undo_history_count", {}, {"count"}),
    # -- actions --
    ("save_project", {}, {"acknowledged", "saved"}),
    ("undo", {"steps": 1}, {"acknowledged", "undone"}),
    ("redo", {}, {"acknowledged", "redo"}),
    ("save_undo", {"undo_name": "test"}, {"acknowledged", "undo_name"}),
    ("restore_undo", {}, {"acknowledged", "restored"}),
    # Project lifecycle (B4)
    ("get_project_path", {}, {"path"}),
    ("get_project_state", {}, {"title", "path"}),
    ("new_project", {}, {"acknowledged", "new_project"}),
    ("close_project", {}, {"acknowledged", "closed"}),
    ("open_project", {"path": "/tmp/test.flp"}, {"acknowledged", "opened"}),
    ("save_project_as", {"path": "/tmp/test.flp"}, {"acknowledged", "saved"}),
]

_DEVICE_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("is_assigned", {}, {"assigned"}),
    ("get_name", {}, {"name"}),
    ("get_port_number", {}, {"port_number"}),
    ("midi_out_msg", {"message": 144}, {"acknowledged", "message"}),
    ("midi_out_sysex", {"message": "F0 7E F7"}, {"acknowledged", "message"}),
]

_ARRANGEMENT_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("get_current_time", {}, {"time"}),
    ("get_time_hint", {"mode": 0, "time": 0}, {"hint", "mode", "time"}),
    ("get_selection_start", {}, {"start"}),
    ("get_selection_end", {}, {"end"}),
    ("jump_to_marker", {"delta": 1}, {"acknowledged", "delta"}),
]

_RENDER_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("export", {"format": "wav"}, {"task_status", "format"}),
    ("get_job", {"job_id": "job-0"}, {"job_id", "status"}),
    ("cancel_job", {"job_id": "job-0"}, {"acknowledged", "cancelled"}),
]

_AUDIO_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("analyze", {"analyzer": "spectrum"}, {"task_status", "analyzer"}),
    ("get_analysis", {"analysis_id": "analysis-0"}, {"analysis_id", "status"}),
    ("cancel_analysis", {"analysis_id": "analysis-0"}, {"acknowledged", "cancelled"}),
]

_AUTOMATION_OPS: list[tuple[str, dict[str, Any], set[str]]] = [
    ("list_clips", {}, {"clips"}),
    ("get_clip", {"clip_index": 0}, {"clip_index", "name"}),
    ("create_clip", {"name": "Volume"}, {"acknowledged", "clip_index"}),
    ("delete_clip", {"clip_index": 0}, {"acknowledged", "deleted"}),
    ("write_points", {"clip_index": 0, "points": []}, {"acknowledged", "points_written"}),
    ("read_points", {"clip_index": 0}, {"clip_index", "points"}),
    (
        "link_to_parameter",
        {"clip_index": 0, "target_type": "mixer", "target_index": 0, "parameter_index": 0},
        {"acknowledged", "linked"},
    ),
]


# ---------------------------------------------------------------------------
# Parametrized test classes — one per domain
# ---------------------------------------------------------------------------


class TestTransportDomain:
    """Transport domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _TRANSPORT_OPS,
        ids=[op for op, _, _ in _TRANSPORT_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("transport", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestMixerDomain:
    """Mixer domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _MIXER_OPS,
        ids=[op for op, _, _ in _MIXER_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("mixer", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestChannelsDomain:
    """Channels domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _CHANNELS_OPS,
        ids=[op for op, _, _ in _CHANNELS_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("channels", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestPatternsDomain:
    """Patterns domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _PATTERNS_OPS,
        ids=[op for op, _, _ in _PATTERNS_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("patterns", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestPlaylistDomain:
    """Playlist domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _PLAYLIST_OPS,
        ids=[op for op, _, _ in _PLAYLIST_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("playlist", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestConnectionDomain:
    """Connection domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _CONNECTION_OPS,
        ids=[op for op, _, _ in _CONNECTION_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("connection", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestMidiDomain:
    """MIDI domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _MIDI_OPS,
        ids=[op for op, _, _ in _MIDI_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("midi", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestPianoRollDomain:
    """Piano-roll domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _PIANO_ROLL_OPS,
        ids=[op for op, _, _ in _PIANO_ROLL_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("piano-roll", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestPluginsDomain:
    """Plugins domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _PLUGINS_OPS,
        ids=[op for op, _, _ in _PLUGINS_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("plugins", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestUiDomain:
    """UI domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _UI_OPS,
        ids=[op for op, _, _ in _UI_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("ui", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestGeneralDomain:
    """General domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _GENERAL_OPS,
        ids=[op for op, _, _ in _GENERAL_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("general", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestDeviceDomain:
    """Device domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _DEVICE_OPS,
        ids=[op for op, _, _ in _DEVICE_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("device", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestArrangementDomain:
    """Arrangement domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _ARRANGEMENT_OPS,
        ids=[op for op, _, _ in _ARRANGEMENT_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("arrangement", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestRenderDomain:
    """Render domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _RENDER_OPS,
        ids=[op for op, _, _ in _RENDER_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("render", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestAudioDomain:
    """Audio domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _AUDIO_OPS,
        ids=[op for op, _, _ in _AUDIO_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("audio", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


class TestAutomationDomain:
    """Automation domain mock handler schema consistency."""

    @pytest.mark.parametrize(
        ("operation", "payload", "required_keys"),
        _AUTOMATION_OPS,
        ids=[op for op, _, _ in _AUTOMATION_OPS],
    )
    def test_schema(self, operation: str, payload: dict[str, Any], required_keys: set[str]) -> None:
        result = _call("automation", operation, payload)
        _assert_base(result)
        _assert_keys(result, required_keys)


# ---------------------------------------------------------------------------
# Cross-cutting: exhaustive coverage of every dispatch entry
# ---------------------------------------------------------------------------


class TestDispatchTableExhaustiveCoverage:
    """Ensure every entry in _MOCK_DISPATCH is covered by the domain tests above."""

    def _all_tested_keys(self) -> set[tuple[str, str]]:
        """Collect every (domain, operation) exercised by the per-domain lists."""
        tested: set[tuple[str, str]] = set()
        for op, _, _ in _TRANSPORT_OPS:
            tested.add(("transport", op))
        for op, _, _ in _MIXER_OPS:
            tested.add(("mixer", op))
        for op, _, _ in _CHANNELS_OPS:
            tested.add(("channels", op))
        for op, _, _ in _PATTERNS_OPS:
            tested.add(("patterns", op))
        for op, _, _ in _PLAYLIST_OPS:
            tested.add(("playlist", op))
        for op, _, _ in _CONNECTION_OPS:
            tested.add(("connection", op))
        for op, _, _ in _MIDI_OPS:
            tested.add(("midi", op))
        for op, _, _ in _PIANO_ROLL_OPS:
            tested.add(("piano-roll", op))
        for op, _, _ in _PLUGINS_OPS:
            tested.add(("plugins", op))
        for op, _, _ in _UI_OPS:
            tested.add(("ui", op))
        for op, _, _ in _GENERAL_OPS:
            tested.add(("general", op))
        for op, _, _ in _DEVICE_OPS:
            tested.add(("device", op))
        for op, _, _ in _ARRANGEMENT_OPS:
            tested.add(("arrangement", op))
        for op, _, _ in _RENDER_OPS:
            tested.add(("render", op))
        for op, _, _ in _AUDIO_OPS:
            tested.add(("audio", op))
        for op, _, _ in _AUTOMATION_OPS:
            tested.add(("automation", op))
        return tested

    def test_no_dispatch_entry_uncovered(self) -> None:
        """Every key in _MOCK_DISPATCH must appear in the domain test lists."""
        tested = self._all_tested_keys()
        dispatch_keys = set(_MOCK_DISPATCH.keys())
        uncovered = dispatch_keys - tested
        assert not uncovered, (
            f"{len(uncovered)} dispatch entries not covered by schema tests: {sorted(uncovered)}"
        )


# ---------------------------------------------------------------------------
# Cross-cutting: JSON-serialization sweep for all dispatch entries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain_op",
    list(_MOCK_DISPATCH.keys()),
    ids=[f"{d}.{o}" for d, o in _MOCK_DISPATCH.keys()],
)
def test_all_results_json_serializable(domain_op: tuple[str, str]) -> None:
    """Every mock result must survive a JSON round-trip without error."""
    domain, operation = domain_op
    result = _call(domain, operation)
    _assert_base(result)


# ---------------------------------------------------------------------------
# Cross-cutting: setter patterns always include "acknowledged"
# ---------------------------------------------------------------------------

_SETTER_PREFIXES = ("set_", "mute", "solo", "arm", "update", "route", "send", "trigger")
_ACTION_OPS = (
    "play",
    "pause",
    "stop",
    "record",
    "rewind",
    "fast_forward",
    "marker_jump",
    "connect",
    "create",
    "create_pattern",
    "rename",
    "rename_pattern",
    "select",
    "select_pattern",
    "select_channel",
    "select_track",
    "duplicate",
    "clone",
    "jump_to",
    "clear",
    "save_project",
    "undo",
    "save_undo",
    "restore_undo",
    "next_preset",
    "prev_preset",
    "previous_preset",
    "show_window",
    "hide_window",
    "next_window",
    "scroll_window",
    "quick_quantize",
    "midi_out_msg",
    "midi_out_sysex",
    "jump_to_marker",
    "delete_notes",
)


@pytest.mark.parametrize(
    "domain_op",
    list(_MOCK_DISPATCH.keys()),
    ids=[f"{d}.{o}" for d, o in _MOCK_DISPATCH.keys()],
)
def test_setter_and_action_results_have_acknowledged(domain_op: tuple[str, str]) -> None:
    """Setters and actions must include ``acknowledged: True``."""
    domain, operation = domain_op
    is_setter = any(operation.startswith(pfx) for pfx in _SETTER_PREFIXES)
    is_action = operation in _ACTION_OPS
    if not (is_setter or is_action):
        pytest.skip("Not a setter/action operation")
    result = _call(domain, operation)
    assert result.get("acknowledged") is True, (
        f"{domain}.{operation} is a setter/action but lacks 'acknowledged': {result}"
    )


# ---------------------------------------------------------------------------
# Cross-cutting: noop operation
# ---------------------------------------------------------------------------


def test_noop_returns_acknowledged_with_noop_flag() -> None:
    """The special ``noop`` operation must return acknowledged + noop."""
    result = mock_result("any_domain", "noop", {"foo": "bar"}, rollback_class=None)
    _assert_base(result)
    assert result["acknowledged"] is True
    assert result["noop"] is True
    assert result["payload"] == {"foo": "bar"}
