"""Dispatch-table mock result generators for the FL Studio bridge.

Each handler receives the operation payload and returns a deterministic
mock result dict.  The public entry point is :func:`mock_result`.
"""

from __future__ import annotations

from collections.abc import Callable

from fl_mcp.schemas import RollbackClass


def _payload_value(payload: dict[str, object], *keys: str, default: object) -> object:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _prop_getter(
    prop: str, default: object, *index_keys: str
) -> Callable[[dict[str, object]], dict[str, object]]:
    """Return a mock handler that reads a single channel/track property."""

    def handler(payload: dict[str, object]) -> dict[str, object]:
        return {
            prop: default,
            "index": _payload_value(payload, *index_keys, default=0),
        }

    return handler


def _prop_setter(
    prop: str, default: object, *index_keys: str
) -> Callable[[dict[str, object]], dict[str, object]]:
    """Return a mock handler that writes a single channel/track property."""

    def handler(payload: dict[str, object]) -> dict[str, object]:
        return {
            "acknowledged": True,
            "index": _payload_value(payload, *index_keys, default=0),
            prop: _payload_value(payload, prop, default=default),
        }

    return handler


# ---------------------------------------------------------------------------
# Individual mock handler functions
# ---------------------------------------------------------------------------


def _mock_noop(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "noop": True, "payload": payload}


def _mock_connection_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        "connected": False,
        "input_port": payload.get("input_port"),
        "output_port": payload.get("output_port"),
        "provider": payload.get("provider", "mock"),
        "mode": "mock",
    }


def _mock_connection_connect(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "connected": True,
        "input_port": payload.get("input_port"),
        "output_port": payload.get("output_port"),
    }


def _mock_midi_list_ports(payload: dict[str, object]) -> dict[str, object]:
    return {"inputs": ["FL Bridge In"], "outputs": ["FL Bridge Out"]}


def _mock_midi_send_note(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "queued": True,
        "message_type": "note",
        "port": payload.get("port"),
        "channel": payload.get("channel", 0),
        "note": payload.get("note"),
        "velocity": payload.get("velocity", 100),
        "duration_beats": payload.get("duration_beats", 1.0),
        "position_beats": payload.get("position_beats"),
    }


def _mock_midi_send_cc(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "queued": True,
        "message_type": "control_change",
        "port": payload.get("port"),
        "channel": payload.get("channel", 0),
        "control": _payload_value(payload, "control", "controller", default=0),
        "value": payload.get("value"),
    }


def _mock_midi_send_program_change(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "queued": True,
        "message_type": "program_change",
        "port": payload.get("port"),
        "channel": payload.get("channel", 0),
        "program": payload.get("program"),
    }


def _mock_midi_send_pitch_bend(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "queued": True,
        "message_type": "pitch_bend",
        "port": payload.get("port"),
        "channel": payload.get("channel", 0),
        "value": payload.get("value"),
    }


def _mock_transport_get_state(payload: dict[str, object]) -> dict[str, object]:
    return {
        "playing": False,
        "recording": False,
        "bpm": 128.0,
        "position_beats": 0.0,
        "loop_mode": "song",
        "playback_speed": 1.0,
    }


def _mock_transport_get_tempo(payload: dict[str, object]) -> dict[str, object]:
    return {"bpm": 128.0}


def _mock_transport_get_song_position(payload: dict[str, object]) -> dict[str, object]:
    return {"position_beats": 0.0}


def _mock_transport_get_length(payload: dict[str, object]) -> dict[str, object]:
    return {"mode": payload.get("mode", "song"), "length_beats": 64.0}


def _mock_transport_play(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "playing": True, "recording": False}


def _mock_transport_pause(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "playing": False, "paused": True}


def _mock_transport_stop(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "playing": False, "recording": False}


def _mock_transport_record(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "playing": True, "recording": True}


def _mock_transport_set_tempo(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "bpm": payload.get("bpm", 128.0)}


def _mock_transport_set_song_position(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "position_beats": payload.get("position_beats", 0.0)}


def _mock_transport_set_loop_mode(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "loop_mode": payload.get("mode", "song")}


def _mock_transport_set_playback_speed(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "playback_speed": payload.get("speed", 1.0)}


def _mock_mixer_list_tracks(payload: dict[str, object]) -> dict[str, object]:
    return {
        "tracks": [
            {
                "track_index": 0,
                "name": "Master",
                "volume": 0.8,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "armed": True,
            }
        ]
    }


def _mock_mixer_get_track(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", default=0)
    return {
        "track_index": track_index,
        "name": f"Track {track_index}",
        "volume": 0.75,
        "pan": 0.0,
        "muted": False,
        "solo": False,
        "armed": False,
    }


def _mock_mixer_get_track_count(payload: dict[str, object]) -> dict[str, object]:
    return {"track_count": 125}


def _mock_mixer_get_meter_level(payload: dict[str, object]) -> dict[str, object]:
    return {
        "track_index": _payload_value(payload, "track_index", default=0),
        "left": 0.42,
        "right": 0.39,
    }


def _mock_mixer_update_track(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", default=0)
    return {
        "acknowledged": True,
        "track": {
            "track_index": track_index,
            "name": payload.get("name", f"Track {track_index}"),
            "volume": payload.get("volume", 0.75),
            "pan": payload.get("pan", 0.0),
            "muted": payload.get("muted", False),
            "solo": payload.get("solo", False),
            "armed": payload.get("armed", False),
            "color": payload.get("color"),
        },
    }


def _mock_mixer_set_stereo_separation(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", default=0)
    return {
        "acknowledged": True,
        "track_index": track_index,
        "stereo_separation": payload.get("stereo_separation", 0.0),
    }


def _mock_mixer_single_field(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", default=0)
    return {"acknowledged": True, "track_index": track_index, "updated_fields": dict(payload)}


def _mock_channels_list(payload: dict[str, object]) -> dict[str, object]:
    return {
        "channels": [
            {
                "channel_index": 0,
                "name": "Kick",
                "volume": 0.8,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "color": 16711680,
            }
        ]
    }


def _mock_channels_get_channel(payload: dict[str, object]) -> dict[str, object]:
    channel_index = _payload_value(payload, "channel_index", default=0)
    return {
        "channel_index": channel_index,
        "name": f"Channel {channel_index}",
        "volume": 0.8,
        "pan": 0.0,
        "muted": False,
        "solo": False,
        "color": 16711680,
        "selected": False,
    }


def _mock_channels_get_selected(payload: dict[str, object]) -> dict[str, object]:
    return {"channel_index": 0, "name": "Kick", "selected": True}


def _mock_channels_get_target_fx_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "mixer_track_index": 1,
    }


def _mock_channels_select_channel(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "exclusive": payload.get("exclusive", False),
        "selected": True,
    }


def _mock_channels_update_channel(payload: dict[str, object]) -> dict[str, object]:
    channel_index = _payload_value(payload, "channel_index", default=0)
    return {
        "acknowledged": True,
        "channel": {
            "channel_index": channel_index,
            "name": payload.get("name", f"Channel {channel_index}"),
            "volume": payload.get("volume", 0.8),
            "pan": payload.get("pan", 0.0),
            "muted": payload.get("muted", False),
            "solo": payload.get("solo", False),
            "color": payload.get("color", 16711680),
        },
    }


def _mock_channels_single_field(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "updated_fields": dict(payload),
    }


def _mock_channels_route_to_mixer(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "mixer_track_index": payload.get("mixer_track_index", 0),
    }


def _mock_channels_get_step_sequence(payload: dict[str, object]) -> dict[str, object]:
    return {
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "steps": [0, 4, 8, 12],
    }


def _mock_channels_set_step_sequence(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "steps": payload.get("steps", []),
    }


def _mock_channels_trigger_note(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "queued": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "note": payload.get("note"),
        "velocity": payload.get("velocity", 100),
        "duration_beats": payload.get("duration_beats", 1.0),
    }


def _mock_channels_set_pitch(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "pitch": payload.get("pitch", 0.0),
    }


def _mock_channels_duplicate(payload: dict[str, object]) -> dict[str, object]:
    source_index = _payload_value(payload, "channel_index", default=0)
    duplicated_index = source_index + 1 if isinstance(source_index, int) else 1
    return {
        "acknowledged": True,
        "source_channel_index": source_index,
        "duplicated_channel_index": duplicated_index,
    }


_mock_channels_get_color = _prop_getter("color", 16711680, "index", "channel_index")
_mock_channels_set_color = _prop_setter("color", 0, "index", "channel_index")
_mock_channels_get_volume = _prop_getter("volume", 0.78, "index", "channel_index")
_mock_channels_set_volume = _prop_setter("volume", 0.78, "index", "channel_index")
_mock_channels_get_pan = _prop_getter("pan", 0.0, "index", "channel_index")
_mock_channels_set_pan = _prop_setter("pan", 0.0, "index", "channel_index")


def _mock_channels_mute(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "channel_index", default=0),
        "value": _payload_value(payload, "value", default=-1),
        "muted": True,
    }


def _mock_channels_solo(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "channel_index", default=0),
        "solo": True,
    }


def _mock_channels_get_type(payload: dict[str, object]) -> dict[str, object]:
    return {
        "type": 0,
        "type_name": "sampler",
        "index": _payload_value(payload, "index", "channel_index", default=0),
    }


def _mock_channels_get_midi_in_port(payload: dict[str, object]) -> dict[str, object]:
    return {
        "midi_in_port": -1,
        "index": _payload_value(payload, "index", "channel_index", default=0),
    }


def _mock_channels_get_grid_bit(payload: dict[str, object]) -> dict[str, object]:
    return {
        "value": False,
        "index": _payload_value(payload, "index", "channel_index", default=0),
        "position": _payload_value(payload, "position", default=0),
    }


def _mock_channels_set_grid_bit(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "channel_index", default=0),
        "position": _payload_value(payload, "position", default=0),
        "value": _payload_value(payload, "value", default=True),
    }


def _mock_channels_quick_quantize(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "channel_index", default=0),
        "start_only": _payload_value(payload, "start_only", default=1),
    }


def _mock_channels_load_sample(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "file_path": _payload_value(payload, "file_path", default=""),
        "loaded": True,
    }


_mock_mixer_get_track_color = _prop_getter("color", 5592575, "index", "track_index")
_mock_mixer_set_track_color = _prop_setter("color", 0, "index", "track_index")
_mock_mixer_get_track_volume = _prop_getter("volume", 0.75, "index", "track_index")
_mock_mixer_set_track_volume = _prop_setter("volume", 0.75, "index", "track_index")
_mock_mixer_get_track_pan = _prop_getter("pan", 0.0, "index", "track_index")
_mock_mixer_set_track_pan = _prop_setter("pan", 0.0, "index", "track_index")


def _mock_mixer_mute_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "value": _payload_value(payload, "value", default=-1),
        "muted": True,
    }


def _mock_mixer_solo_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "value": _payload_value(payload, "value", default=-1),
        "solo": True,
    }


def _mock_mixer_arm_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "armed": True,
    }


def _mock_mixer_is_track_armed(payload: dict[str, object]) -> dict[str, object]:
    return {
        "armed": False,
        "index": _payload_value(payload, "index", "track_index", default=0),
    }


def _mock_mixer_set_route_to(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "dest_index": _payload_value(payload, "dest_index", default=0),
        "value": _payload_value(payload, "value", default=True),
    }


def _mock_mixer_get_route_send_level(payload: dict[str, object]) -> dict[str, object]:
    return {
        "level": 0.8,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "dest_index": _payload_value(payload, "dest_index", default=0),
    }


def _mock_mixer_set_route_send_level(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "dest_index": _payload_value(payload, "dest_index", default=0),
        "level": _payload_value(payload, "level", default=0.8),
    }


def _mock_mixer_get_eq_gain(payload: dict[str, object]) -> dict[str, object]:
    return {
        "value": 0.0,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "band": _payload_value(payload, "band", default=0),
    }


def _mock_mixer_set_eq_gain(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "band": _payload_value(payload, "band", default=0),
        "value": _payload_value(payload, "value", default=0.0),
    }


def _mock_mixer_get_eq_frequency(payload: dict[str, object]) -> dict[str, object]:
    return {
        "value": 1000.0,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "band": _payload_value(payload, "band", default=0),
    }


def _mock_mixer_set_eq_frequency(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "band": _payload_value(payload, "band", default=0),
        "value": _payload_value(payload, "value", default=1000.0),
    }


def _mock_mixer_get_eq_bandwidth(payload: dict[str, object]) -> dict[str, object]:
    return {
        "value": 1.0,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "band": _payload_value(payload, "band", default=0),
    }


def _mock_mixer_get_slot_count(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", default=0)
    return {"track_index": track_index, "slot_count": 10}


def _mock_mixer_get_slot_name(payload: dict[str, object]) -> dict[str, object]:
    return {
        "track_index": _payload_value(payload, "track_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=0),
        "name": "",
        "empty": True,
    }


def _mock_mixer_is_slot_enabled(payload: dict[str, object]) -> dict[str, object]:
    return {
        "track_index": _payload_value(payload, "track_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=0),
        "enabled": True,
    }


def _mock_mixer_enable_slot(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "track_index": _payload_value(payload, "track_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=0),
        "enabled": _payload_value(payload, "enabled", default=True),
    }


def _mock_mixer_get_slot_plugin(payload: dict[str, object]) -> dict[str, object]:
    return {
        "track_index": _payload_value(payload, "track_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=0),
        "plugin_name": "",
        "plugin_type": None,
        "parameter_count": 0,
        "empty": True,
    }


def _mock_mixer_set_slot_plugin(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "track_index": _payload_value(payload, "track_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=0),
        "plugin_name": _payload_value(payload, "plugin_name", default=""),
    }


def _mock_transport_rewind(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "start_stop": _payload_value(payload, "start_stop", default=1),
        "rewinding": True,
    }


def _mock_transport_fast_forward(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "start_stop": _payload_value(payload, "start_stop", default=1),
        "fast_forwarding": True,
    }


def _mock_transport_is_recording(payload: dict[str, object]) -> dict[str, object]:
    return {"recording": False}


def _mock_transport_get_song_pos_hint(payload: dict[str, object]) -> dict[str, object]:
    return {"hint": "Bar 1:Beat 1:Tick 0"}


def _mock_transport_marker_jump(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "value": _payload_value(payload, "value", default=1),
        "jumped": True,
    }


def _mock_transport_get_time_signature(payload: dict[str, object]) -> dict[str, object]:
    return {"numerator": 4, "denominator": 4}


def _mock_transport_set_time_signature(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "numerator": _payload_value(payload, "numerator", default=4),
        "denominator": _payload_value(payload, "denominator", default=4),
    }


def _mock_transport_get_swing(payload: dict[str, object]) -> dict[str, object]:
    return {"value": 0.0, "swing_percent": 0}


def _mock_transport_set_swing(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "value": _payload_value(payload, "value", default=0.0),
    }


def _mock_patterns_list(payload: dict[str, object]) -> dict[str, object]:
    return {"patterns": [{"pattern_index": 1, "name": "Intro"}]}


def _mock_patterns_select(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "pattern_index": payload.get("pattern_index", 1),
        "selected": True,
    }


def _mock_patterns_create(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "pattern": {
            "pattern_index": 2,
            "name": payload.get("name", "Pattern 2"),
        },
    }


def _mock_patterns_rename(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "pattern": {
            "pattern_index": payload.get("pattern_index", 1),
            "name": payload.get("name", "Renamed Pattern"),
        },
    }


def _mock_patterns_set_length(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "updated_fields": dict(payload)}


def _mock_patterns_get_color(payload: dict[str, object]) -> dict[str, object]:
    return {
        "color": 16711680,
        "index": _payload_value(payload, "index", "pattern_index", default=0),
    }


def _mock_patterns_set_color(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "pattern_index", default=0),
        "color": _payload_value(payload, "color", default=0),
    }


def _mock_patterns_clone(payload: dict[str, object]) -> dict[str, object]:
    source_index = _payload_value(payload, "index", default=None)
    return {
        "acknowledged": True,
        "source_index": source_index,
        "cloned_pattern_index": 3,
    }


def _mock_patterns_jump_to(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "pattern_index", default=0),
        "jumped": True,
    }


def _mock_patterns_is_default(payload: dict[str, object]) -> dict[str, object]:
    return {
        "is_default": True,
        "index": _payload_value(payload, "index", "pattern_index", default=0),
    }


def _mock_playlist_list_tracks(payload: dict[str, object]) -> dict[str, object]:
    return {"tracks": [{"track_index": 1, "name": "Playlist 1"}]}


def _mock_playlist_get_track(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", "playlist_track_index", default=1)
    return {"track_index": track_index, "name": f"Playlist {track_index}"}


def _mock_playlist_update_track(payload: dict[str, object]) -> dict[str, object]:
    track_index = _payload_value(payload, "track_index", "playlist_track_index", default=1)
    return {
        "acknowledged": True,
        "track": {
            "track_index": track_index,
            "name": payload.get("name", f"Playlist {track_index}"),
        },
    }


_mock_playlist_get_track_color = _prop_getter("color", 65280, "index", "track_index")
_mock_playlist_set_track_color = _prop_setter("color", 0, "index", "track_index")


def _mock_playlist_mute_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "value": _payload_value(payload, "value", default=-1),
        "muted": True,
    }


def _mock_playlist_solo_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "value": _payload_value(payload, "value", default=-1),
        "solo": True,
    }


def _mock_playlist_select_track(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", "track_index", default=0),
        "selected": True,
    }


def _mock_playlist_get_track_activity(payload: dict[str, object]) -> dict[str, object]:
    return {
        "activity": 0.73,
        "index": _payload_value(payload, "index", "track_index", default=0),
    }


def _mock_playlist_list_clips(payload: dict[str, object]) -> dict[str, object]:
    return {
        "clips": [
            {"clip_index": 0, "track_index": 1, "position": 0.0, "length": 4.0, "pattern_index": 0}
        ]
    }


def _mock_playlist_place_clip(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "track_index": _payload_value(payload, "track_index", default=1),
        "position": _payload_value(payload, "position", "start_beats", default=0.0),
        "pattern_index": _payload_value(payload, "pattern_index", default=0),
    }


def _mock_playlist_move_clip(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "new_position": _payload_value(
            payload, "new_position", "destination_start_beats", default=0.0
        ),
        "new_track_index": _payload_value(
            payload, "new_track_index", "destination_track_index", default=1
        ),
    }


def _mock_playlist_delete_clip(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "deleted": True,
    }


def _mock_playlist_list_markers(payload: dict[str, object]) -> dict[str, object]:
    return {"markers": [{"marker_index": 0, "name": "Intro", "position": 0.0}]}


def _mock_playlist_create_marker(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "marker_index": 1,
        "name": _payload_value(payload, "name", default="Marker"),
        "position": _payload_value(payload, "position", "position_beats", default=0.0),
    }


def _mock_playlist_update_marker(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "marker_index": _payload_value(payload, "marker_index", default=0),
        "name": _payload_value(payload, "name", default="Marker"),
        "position": _payload_value(payload, "position", "position_beats", default=0.0),
    }


def _mock_playlist_delete_marker(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "marker_index": _payload_value(payload, "marker_index", default=0),
        "deleted": True,
    }


def _mock_playlist_get_arrangement(payload: dict[str, object]) -> dict[str, object]:
    return {
        "track_count": 2,
        "clip_count": 1,
        "marker_count": 1,
        "length_beats": 32.0,
    }


def _mock_piano_roll_get_state(payload: dict[str, object]) -> dict[str, object]:
    return {
        "ppq": 96,
        "notes": [
            {"note": 60, "velocity": 100, "length_beats": 1.0, "position_beats": 0.0},
        ],
    }


def _mock_piano_roll_send_notes(payload: dict[str, object]) -> dict[str, object]:
    notes = payload.get("notes")
    note_list = notes if isinstance(notes, list) else []
    return {
        "acknowledged": True,
        "mode": payload.get("mode", "append"),
        "note_count": len(note_list),
        "notes": note_list,
    }


def _mock_piano_roll_delete_notes(payload: dict[str, object]) -> dict[str, object]:
    notes = payload.get("notes")
    note_list = notes if isinstance(notes, list) else []
    return {
        "acknowledged": True,
        "deleted_count": len(note_list),
        "notes": note_list,
    }


def _mock_piano_roll_clear(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "cleared": True}


def _mock_piano_roll_quantize(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "notes_quantized": 0,
        "grid": _payload_value(payload, "grid", default="1/4"),
    }


def _mock_piano_roll_transpose(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "semitones": _payload_value(payload, "semitones", default=0),
    }


def _mock_piano_roll_humanize(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "variance": _payload_value(payload, "variance", default=0.1),
        "notes_affected": 0,
    }


def _mock_piano_roll_generate_chords(payload: dict[str, object]) -> dict[str, object]:
    root = _payload_value(payload, "root", "root_note", default="C")
    scale = _payload_value(payload, "scale", default="major")
    bars = _payload_value(payload, "bars", default=4)
    return {
        "acknowledged": True,
        "generated": True,
        "root": root,
        "scale": scale,
        "bars": bars,
        "notes": [
            {"note": 60, "time": 0.0, "duration": 1.0, "velocity": 80},
            {"note": 64, "time": 0.0, "duration": 1.0, "velocity": 75},
            {"note": 67, "time": 0.0, "duration": 1.0, "velocity": 75},
            {"note": 62, "time": 1.0, "duration": 1.0, "velocity": 80},
            {"note": 65, "time": 1.0, "duration": 1.0, "velocity": 75},
            {"note": 69, "time": 1.0, "duration": 1.0, "velocity": 75},
        ],
    }


def _mock_piano_roll_generate_melody(payload: dict[str, object]) -> dict[str, object]:
    root = _payload_value(payload, "root", "root_note", default="C")
    scale = _payload_value(payload, "scale", default="major")
    bars = _payload_value(payload, "bars", default=4)
    return {
        "acknowledged": True,
        "generated": True,
        "root": root,
        "scale": scale,
        "bars": bars,
        "notes": [
            {"note": 60, "time": 0.0, "duration": 0.5, "velocity": 90},
            {"note": 62, "time": 0.5, "duration": 0.5, "velocity": 80},
            {"note": 64, "time": 1.0, "duration": 0.5, "velocity": 85},
            {"note": 65, "time": 1.5, "duration": 0.5, "velocity": 80},
            {"note": 67, "time": 2.0, "duration": 1.0, "velocity": 95},
            {"note": 65, "time": 3.0, "duration": 0.5, "velocity": 80},
            {"note": 64, "time": 3.5, "duration": 0.5, "velocity": 75},
        ],
    }


def _mock_piano_roll_generate_bass(payload: dict[str, object]) -> dict[str, object]:
    root = _payload_value(payload, "root", "root_note", default="C")
    scale = _payload_value(payload, "scale", default="major")
    bars = _payload_value(payload, "bars", default=4)
    return {
        "acknowledged": True,
        "generated": True,
        "root": root,
        "scale": scale,
        "bars": bars,
        "notes": [
            {"note": 36, "time": 0.0, "duration": 0.25, "velocity": 100},
            {"note": 36, "time": 0.5, "duration": 0.25, "velocity": 90},
            {"note": 38, "time": 1.0, "duration": 0.25, "velocity": 100},
            {"note": 38, "time": 1.5, "duration": 0.25, "velocity": 90},
            {"note": 36, "time": 2.0, "duration": 0.5, "velocity": 100},
            {"note": 41, "time": 3.0, "duration": 0.25, "velocity": 90},
            {"note": 43, "time": 3.5, "duration": 0.25, "velocity": 85},
        ],
    }


def _mock_plugins_list_plugins(payload: dict[str, object]) -> dict[str, object]:
    channel_index = _payload_value(payload, "channel_index", default=0)
    plugin_slot = _payload_value(payload, "plugin_slot", "slot_index", default=0)
    return {
        "plugins": [
            {
                "channel_index": channel_index,
                "plugin_slot": plugin_slot,
                "name": f"Plugin {plugin_slot}",
            }
        ]
    }


def _mock_plugins_get_parameters(payload: dict[str, object]) -> dict[str, object]:
    return {
        "parameters": [
            {"parameter_index": 0, "name": "Cutoff", "value": 0.5},
            {"parameter_index": 1, "name": "Resonance", "value": 0.25},
            {"parameter_index": 2, "name": "Macro 1", "value": 0.75},
            {"parameter_index": 3, "name": "Output Gain", "value": 0.5},
        ]
    }


def _mock_plugins_get_parameter(payload: dict[str, object]) -> dict[str, object]:
    return {
        "parameter": _payload_value(payload, "parameter", "parameter_id", default="cutoff"),
        "parameter_index": _payload_value(payload, "parameter_index", "param_index", default=0),
        "value": 0.5,
    }


def _mock_plugins_set_parameter(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "parameter": _payload_value(payload, "parameter", "parameter_id", default="cutoff"),
        "value": payload.get("value", 0.5),
    }


def _mock_plugins_next_preset(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "preset_direction": "next"}


def _mock_plugins_prev_preset(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "preset_direction": "previous"}


def _mock_plugins_get_preset_name(payload: dict[str, object]) -> dict[str, object]:
    preset_index = _payload_value(payload, "preset_index", "parameter_index", default=0)
    return {
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "preset_index": preset_index,
        "preset_name": f"Preset {preset_index}",
    }


def _mock_plugins_load_preset_by_name(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", default=0),
        "preset_name": _payload_value(payload, "preset_name", default=""),
        "loaded": True,
    }


def _mock_plugins_get_param_value_string(payload: dict[str, object]) -> dict[str, object]:
    return {
        "value_string": "50%",
        "param_index": _payload_value(payload, "param_index", default=0),
    }


def _mock_plugins_get_parameter_name(payload: dict[str, object]) -> dict[str, object]:
    raw_index = _payload_value(payload, "parameter_index", "param_index", default=0)
    parameter_index = (
        raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else 0
    )
    names = ("Cutoff", "Resonance", "Macro 1", "Output Gain")
    return {
        "parameter_index": parameter_index,
        "parameter_name": names[parameter_index % len(names)],
    }


def _mock_plugins_get_color(payload: dict[str, object]) -> dict[str, object]:
    return {
        "color": 16711680,
        "index": _payload_value(payload, "index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=-1),
    }


def _mock_plugins_get_pad_info(payload: dict[str, object]) -> dict[str, object]:
    return {
        "pad_info": 0,
        "chan_index": _payload_value(payload, "chan_index", default=0),
        "slot_index": _payload_value(payload, "slot_index", default=-1),
        "param_option": _payload_value(payload, "param_option", default=0),
        "param_index": _payload_value(payload, "param_index", default=-1),
    }


def _mock_plugins_is_valid(payload: dict[str, object]) -> dict[str, object]:
    return {
        "is_valid": True,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
    }


def _mock_plugins_get_name(payload: dict[str, object]) -> dict[str, object]:
    return {
        "name": "Fruity Loops Sampler",
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
    }


def _mock_plugins_get_parameter_count(payload: dict[str, object]) -> dict[str, object]:
    return {
        "parameter_count": 4,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
    }


def _mock_plugins_get_preset_count(payload: dict[str, object]) -> dict[str, object]:
    return {
        "preset_count": 0,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
    }


def _mock_plugins_show_window(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
        "visible": True,
    }


def _mock_plugins_load(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
        "plugin_name": _payload_value(payload, "plugin_name", "name", default=""),
        "loaded": True,
    }


def _mock_plugins_replace(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "channel_index": _payload_value(payload, "channel_index", "chan_index", default=0),
        "plugin_name": _payload_value(payload, "plugin_name", "name", default=""),
        "replaced": True,
    }


def _mock_ui_get_visibility(payload: dict[str, object]) -> dict[str, object]:
    return {"window": payload.get("window", "mixer"), "visible": True}


def _mock_ui_show_window(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "window": payload.get("window", "mixer"),
        "visible": payload.get("visible", True),
    }


def _mock_ui_hide_window(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "window": payload.get("window", "mixer"),
        "visible": False,
    }


def _mock_ui_get_focused(payload: dict[str, object]) -> dict[str, object]:
    return {"index": _payload_value(payload, "index", default=0), "focused": True}


def _mock_ui_set_focused(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", default=0),
        "focused": True,
    }


def _mock_ui_get_focused_form_caption(payload: dict[str, object]) -> dict[str, object]:
    return {"caption": "Mixer"}


def _mock_ui_get_focused_plugin_name(payload: dict[str, object]) -> dict[str, object]:
    return {"plugin_name": "Sytrus"}


def _mock_ui_scroll_window(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "index": _payload_value(payload, "index", default=0),
        "value": _payload_value(payload, "value", default=0),
        "direction_flag": _payload_value(payload, "direction_flag", default=0),
    }


def _mock_ui_next_window(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "switched": True}


def _mock_ui_get_snap_mode(payload: dict[str, object]) -> dict[str, object]:
    return {"snap_mode": 3}


def _mock_ui_set_snap_mode(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "snap_mode": _payload_value(payload, "value", default=3),
    }


def _mock_ui_get_hint_msg(payload: dict[str, object]) -> dict[str, object]:
    return {"hint_msg": ""}


def _mock_ui_set_hint_msg(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "msg": _payload_value(payload, "msg", default=""),
    }


def _mock_ui_get_step_edit_mode(payload: dict[str, object]) -> dict[str, object]:
    return {"step_edit_mode": 0}


def _mock_general_get_version(payload: dict[str, object]) -> dict[str, object]:
    return {"version": "FL Studio Mock", "build": "mock"}


def _mock_general_get_project_title(payload: dict[str, object]) -> dict[str, object]:
    return {"title": "Mock Project", "dirty": False}


def _mock_general_save_project(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "saved": True,
        "path": _payload_value(payload, "path", default=None),
    }


def _mock_general_undo(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "steps": payload.get("steps", 1), "undone": True}


def _mock_general_redo(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "redo": True}


def _mock_general_get_changed_flag(payload: dict[str, object]) -> dict[str, object]:
    return {"changed": 1}


def _mock_general_get_rec_ppq(payload: dict[str, object]) -> dict[str, object]:
    return {"ppq": 96}


def _mock_general_get_metronome(payload: dict[str, object]) -> dict[str, object]:
    return {"metronome": False}


def _mock_general_get_precount(payload: dict[str, object]) -> dict[str, object]:
    return {"precount": False}


def _mock_general_save_undo(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "undo_name": _payload_value(payload, "undo_name", default="MCP operation"),
        "flags": _payload_value(payload, "flags", default=0),
    }


def _mock_general_restore_undo(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "restored": True}


def _mock_general_get_undo_history_pos(payload: dict[str, object]) -> dict[str, object]:
    return {"position": 5}


def _mock_general_get_undo_history_count(payload: dict[str, object]) -> dict[str, object]:
    return {"count": 10}


def _mock_general_new_project(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "new_project": True,
        "save_current": _payload_value(payload, "save_current", default=False),
    }


def _mock_general_close_project(payload: dict[str, object]) -> dict[str, object]:
    return {"acknowledged": True, "closed": True}


def _mock_general_get_project_path(payload: dict[str, object]) -> dict[str, object]:
    return {"path": "/mock/projects/untitled.flp", "saved": True}


def _mock_general_get_project_state(payload: dict[str, object]) -> dict[str, object]:
    return {
        "title": "Untitled",
        "path": "/mock/projects/untitled.flp",
        "changed": False,
        "version": "21.0",
    }


def _mock_general_open_project(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "path": _payload_value(payload, "path", default="/mock/projects/untitled.flp"),
        "opened": True,
    }


def _mock_general_save_project_as(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "path": _payload_value(payload, "path", default="/mock/projects/untitled.flp"),
        "saved": True,
    }


def _mock_device_is_assigned(payload: dict[str, object]) -> dict[str, object]:
    return {"assigned": True}


def _mock_device_get_name(payload: dict[str, object]) -> dict[str, object]:
    return {"name": "MIDI Controller"}


def _mock_device_get_port_number(payload: dict[str, object]) -> dict[str, object]:
    return {"port_number": 0}


def _mock_device_midi_out_msg(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "message": _payload_value(payload, "message", default=144),
    }


def _mock_device_midi_out_sysex(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "message": _payload_value(payload, "message", default=""),
    }


def _mock_arrangement_get_current_time(payload: dict[str, object]) -> dict[str, object]:
    return {
        "time": 0,
        "snap": _payload_value(payload, "snap", default=0),
    }


def _mock_arrangement_get_time_hint(payload: dict[str, object]) -> dict[str, object]:
    return {
        "hint": "Bar 1:Beat 1",
        "mode": _payload_value(payload, "mode", default=0),
        "time": _payload_value(payload, "time", default=0),
    }


def _mock_arrangement_get_selection_start(payload: dict[str, object]) -> dict[str, object]:
    return {"start": 0}


def _mock_arrangement_get_selection_end(payload: dict[str, object]) -> dict[str, object]:
    return {"end": 0}


def _mock_arrangement_jump_to_marker(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "delta": _payload_value(payload, "delta", default=1),
    }


def _mock_render_export(payload: dict[str, object]) -> dict[str, object]:
    return {
        "task_status": "queued",
        "output_path": _payload_value(payload, "output_path", "path", default=None),
        "format": payload.get("format", "wav"),
        "tail_seconds": payload.get("tail_seconds", 0),
    }


def _mock_render_get_job(payload: dict[str, object]) -> dict[str, object]:
    job_id = _payload_value(payload, "job_id", default="mock-job-0")
    return {
        "job_id": job_id,
        "status": "completed",
        "progress": 1.0,
        "artifact_uri": None,
    }


def _mock_render_cancel_job(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "job_id": _payload_value(payload, "job_id", default="mock-job-0"),
        "cancelled": True,
    }


def _mock_audio_analyze(payload: dict[str, object]) -> dict[str, object]:
    return {
        "task_status": "queued",
        "analyzer": payload.get("analyzer", "spectrum"),
        "input_path": _payload_value(payload, "input_path", "path", default=None),
        "source": payload.get(
            "source",
            "file" if payload.get("input_path") or payload.get("path") else "last_render",
        ),
    }


def _mock_audio_get_analysis(payload: dict[str, object]) -> dict[str, object]:
    analysis_id = _payload_value(payload, "analysis_id", default="mock-audio-job-0")
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "progress": 1.0,
        "result": {"peak_db": -6.0, "rms_db": -18.0, "duration_seconds": 4.0},
    }


def _mock_audio_cancel_analysis(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "analysis_id": _payload_value(payload, "analysis_id", default="mock-audio-job-0"),
        "cancelled": True,
    }


# ---------------------------------------------------------------------------
# Automation domain mock handlers
# ---------------------------------------------------------------------------


def _mock_automation_list_clips(payload: dict[str, object]) -> dict[str, object]:
    return {
        "clips": [
            {"clip_index": 0, "name": "Volume Automation", "linked": False, "point_count": 4},
        ]
    }


def _mock_automation_get_clip(payload: dict[str, object]) -> dict[str, object]:
    clip_index = _payload_value(payload, "clip_index", default=0)
    return {
        "clip_index": clip_index,
        "name": f"Automation Clip {clip_index}",
        "linked": False,
        "target_type": None,
        "target_index": None,
        "parameter_index": None,
        "point_count": 0,
    }


def _mock_automation_create_clip(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "clip_index": 1,
        "name": _payload_value(payload, "name", default="New Automation Clip"),
        "channel_index": _payload_value(payload, "channel_index", default=None),
    }


def _mock_automation_delete_clip(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "deleted": True,
    }


def _mock_automation_write_points(payload: dict[str, object]) -> dict[str, object]:
    points = payload.get("points")
    point_list = points if isinstance(points, list) else []
    return {
        "acknowledged": True,
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "points_written": len(point_list),
    }


def _mock_automation_read_points(payload: dict[str, object]) -> dict[str, object]:
    return {
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "points": [
            {"time": 0.0, "value": 0.0},
            {"time": 1.0, "value": 0.5},
            {"time": 2.0, "value": 1.0},
            {"time": 4.0, "value": 0.0},
        ],
    }


def _mock_automation_link_to_parameter(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "clip_index": _payload_value(payload, "clip_index", default=0),
        "target_type": _payload_value(payload, "target_type", default="mixer"),
        "target_index": _payload_value(payload, "target_index", default=0),
        "parameter_index": _payload_value(payload, "parameter_index", default=0),
        "linked": True,
    }


def _mock_plugins_inventory_scan(payload: dict[str, object]) -> dict[str, object]:
    return {
        "inventory": [
            {
                "plugin_id": "lennardigital.sylenth1",
                "display_name": "Sylenth1",
                "status": "installed",
            }
        ],
        "profiles": ["lennardigital.sylenth1"],
        "presets": [],
        "query": _payload_value(payload, "query", default=None),
    }


def _mock_plugins_list_profiles(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profiles": [
            {
                "profile_id": "lennardigital.sylenth1",
                "display_name": "Sylenth1",
                "status": "seed",
            }
        ],
        "count": 1,
        "query": _payload_value(payload, "query", default=None),
    }


def _mock_plugins_get_profile(payload: dict[str, object]) -> dict[str, object]:
    profile_id = _payload_value(payload, "profile_id", default="lennardigital.sylenth1")
    return {
        "profile_id": profile_id,
        "profile": {"profile_id": profile_id, "status": "seed"},
        "calibration_status": "required",
    }


def _mock_plugins_resolve_profile(payload: dict[str, object]) -> dict[str, object]:
    return {
        "query": _payload_value(payload, "query", default="sylenth"),
        "matches": [
            {
                "type": "profile",
                "profile": {"profile_id": "lennardigital.sylenth1"},
            }
        ],
    }


def _mock_plugins_probe_instance(payload: dict[str, object]) -> dict[str, object]:
    return {
        "is_valid": True,
        "name": "Sylenth1",
        "parameter_count": 512,
        "channel_index": _payload_value(payload, "channel_index", default=0),
    }


def _mock_plugins_enumerate_parameters(payload: dict[str, object]) -> dict[str, object]:
    return {
        "plugin_name": "Sylenth1",
        "parameter_count": 4,
        "parameters": [
            {
                "parameter_index": index,
                "parameter_name": name,
                "normalized_value": 0.5,
                "value_string": "50%",
                "readable": True,
                "writable": None,
                "write_probe_status": "not_run",
                "risk": "safe",
                "control_origin": "live_raw",
            }
            for index, name in enumerate(("Cutoff", "Resonance", "Macro 1", "Output Gain"))
        ],
        "cursor": _payload_value(payload, "cursor", default=0),
        "next_cursor": None,
        "partial": False,
    }


def _mock_plugins_probe_loadability(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "support_state": "loadable",
        "parameter_count": 4,
        "failures": [],
    }


def _mock_plugins_generate_raw_profile(payload: dict[str, object]) -> dict[str, object]:
    profile_id = _payload_value(payload, "profile_id", default="lennardigital.sylenth1")
    return {
        "raw_profile": {
            "profile_id": profile_id,
            "display_name": "Sylenth1",
            "family": "Sylenth1",
            "semantic_controls": [
                {
                    "control_id": "param.0000.cutoff",
                    "label": "Cutoff",
                    "parameter_index": 0,
                    "parameter_name_hint": "Cutoff",
                    "control_origin": "live_raw",
                }
            ],
            "raw_parameters": _mock_plugins_enumerate_parameters(payload)["parameters"],
            "support_state": "raw_enumerated",
        },
        "persistence": "not_written",
    }


def _mock_plugins_verify_profile_controls(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "verified_controls": [],
        "failures": [],
    }


def _mock_plugins_write_calibration_overlay(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "calibration": {
            "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
            "format": _payload_value(payload, "plugin_format", default="unknown"),
            "mapped_controls": _payload_value(payload, "mapped_controls", default={}),
        },
        "persistence": "written" if payload.get("persist", True) else "not_written",
    }


def _mock_plugins_priority_support_audit(payload: dict[str, object]) -> dict[str, object]:
    return {
        "counts_by_priority": {"P0_paid_installed": 1},
        "counts_by_support_state": {"semantic_seed": 1},
        "blocking_count": 0,
        "blockers": [],
        "rows": [
            {
                "plugin_id": "lennardigital.sylenth1",
                "display_name": "Sylenth1",
                "priority": "P0_paid_installed",
                "support_state": "semantic_seed",
                "inventory_status": "installed",
                "profile_id": "lennardigital.sylenth1",
            }
        ],
    }


def _mock_plugins_export_support_matrix(payload: dict[str, object]) -> dict[str, object]:
    audit = _mock_plugins_priority_support_audit(payload)
    rows = audit.get("rows")
    matrix_rows = rows if isinstance(rows, list) else []
    return {"rows": matrix_rows, "count": len(matrix_rows)}


def _mock_plugins_learn_parameter(payload: dict[str, object]) -> dict[str, object]:
    control_id = _payload_value(payload, "control_id", default="filter.cutoff")
    parameter_index = _payload_value(payload, "observed_parameter_index", default=0)
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "control_id": control_id,
        "calibration": {"mapped_controls": {str(control_id): parameter_index}},
        "persistence": "not_written",
    }


def _mock_plugins_validate_profile(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "ready_for_mapped_execution": False,
        "failure_code": "calibration_required",
    }


def _mock_plugins_get_mapped_parameter(payload: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "control_id": _payload_value(payload, "control_id", default="filter.cutoff"),
        "parameter_index": 0,
        "value": 0.5,
    }


def _mock_plugins_set_mapped_parameter(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "control_id": _payload_value(payload, "control_id", default="filter.cutoff"),
        "parameter_index": 0,
        "value": _payload_value(payload, "value", default=0.5),
    }


def _mock_plugins_load_profile_preset(payload: dict[str, object]) -> dict[str, object]:
    return {
        "acknowledged": True,
        "profile_id": _payload_value(payload, "profile_id", default="lennardigital.sylenth1"),
        "preset_name": _payload_value(payload, "preset_name", default="Default"),
        "loaded": True,
    }


def _mock_plugins_list_local_presets(payload: dict[str, object]) -> dict[str, object]:
    return {
        "presets": [],
        "count": 0,
        "query": _payload_value(payload, "query", default=None),
    }


def _mock_plugins_reconcile_inventory(payload: dict[str, object]) -> dict[str, object]:
    return {
        "by_status": {"installed": ["lennardigital.sylenth1"]},
        "counts": {"installed": 1},
        "query": _payload_value(payload, "query", default=None),
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_MOCK_DISPATCH: dict[tuple[str, str], Callable[[dict[str, object]], dict[str, object]]] = {
    ("connection", "status"): _mock_connection_status,
    ("connection", "connect"): _mock_connection_connect,
    ("midi", "list_ports"): _mock_midi_list_ports,
    ("midi", "send_note"): _mock_midi_send_note,
    ("midi", "send_cc"): _mock_midi_send_cc,
    ("midi", "send_program_change"): _mock_midi_send_program_change,
    ("midi", "send_pitch_bend"): _mock_midi_send_pitch_bend,
    ("transport", "get_state"): _mock_transport_get_state,
    ("transport", "get_playback_state"): _mock_transport_get_state,
    ("transport", "get_tempo"): _mock_transport_get_tempo,
    ("transport", "get_song_position"): _mock_transport_get_song_position,
    ("transport", "get_length"): _mock_transport_get_length,
    ("transport", "play"): _mock_transport_play,
    ("transport", "pause"): _mock_transport_pause,
    ("transport", "stop"): _mock_transport_stop,
    ("transport", "record"): _mock_transport_record,
    ("transport", "set_tempo"): _mock_transport_set_tempo,
    ("transport", "set_song_position"): _mock_transport_set_song_position,
    ("transport", "set_loop_mode"): _mock_transport_set_loop_mode,
    ("transport", "set_playback_speed"): _mock_transport_set_playback_speed,
    ("transport", "rewind"): _mock_transport_rewind,
    ("transport", "fast_forward"): _mock_transport_fast_forward,
    ("transport", "is_recording"): _mock_transport_is_recording,
    ("transport", "get_song_pos_hint"): _mock_transport_get_song_pos_hint,
    ("transport", "marker_jump"): _mock_transport_marker_jump,
    ("transport", "get_time_signature"): _mock_transport_get_time_signature,
    ("transport", "set_time_signature"): _mock_transport_set_time_signature,
    ("transport", "get_swing"): _mock_transport_get_swing,
    ("transport", "set_swing"): _mock_transport_set_swing,
    ("mixer", "list_tracks"): _mock_mixer_list_tracks,
    ("mixer", "get_track"): _mock_mixer_get_track,
    ("mixer", "get_track_info"): _mock_mixer_get_track,
    ("mixer", "get_track_count"): _mock_mixer_get_track_count,
    ("mixer", "get_meter_level"): _mock_mixer_get_meter_level,
    ("mixer", "update_track"): _mock_mixer_update_track,
    ("mixer", "set_stereo_separation"): _mock_mixer_set_stereo_separation,
    ("mixer", "set_volume"): _mock_mixer_single_field,
    ("mixer", "set_pan"): _mock_mixer_single_field,
    ("mixer", "mute"): _mock_mixer_single_field,
    ("mixer", "solo"): _mock_mixer_single_field,
    ("mixer", "set_name"): _mock_mixer_single_field,
    ("mixer", "get_track_color"): _mock_mixer_get_track_color,
    ("mixer", "set_track_color"): _mock_mixer_set_track_color,
    ("mixer", "get_track_volume"): _mock_mixer_get_track_volume,
    ("mixer", "set_track_volume"): _mock_mixer_set_track_volume,
    ("mixer", "get_track_pan"): _mock_mixer_get_track_pan,
    ("mixer", "set_track_pan"): _mock_mixer_set_track_pan,
    ("mixer", "mute_track"): _mock_mixer_mute_track,
    ("mixer", "solo_track"): _mock_mixer_solo_track,
    ("mixer", "arm_track"): _mock_mixer_arm_track,
    ("mixer", "is_track_armed"): _mock_mixer_is_track_armed,
    ("mixer", "set_route_to"): _mock_mixer_set_route_to,
    ("mixer", "get_route_send_level"): _mock_mixer_get_route_send_level,
    ("mixer", "set_route_send_level"): _mock_mixer_set_route_send_level,
    ("mixer", "get_eq_gain"): _mock_mixer_get_eq_gain,
    ("mixer", "set_eq_gain"): _mock_mixer_set_eq_gain,
    ("mixer", "get_eq_frequency"): _mock_mixer_get_eq_frequency,
    ("mixer", "set_eq_frequency"): _mock_mixer_set_eq_frequency,
    ("mixer", "get_eq_bandwidth"): _mock_mixer_get_eq_bandwidth,
    ("mixer", "get_slot_count"): _mock_mixer_get_slot_count,
    ("mixer", "get_slot_name"): _mock_mixer_get_slot_name,
    ("mixer", "is_slot_enabled"): _mock_mixer_is_slot_enabled,
    ("mixer", "enable_slot"): _mock_mixer_enable_slot,
    ("mixer", "get_slot_plugin"): _mock_mixer_get_slot_plugin,
    ("mixer", "set_slot_plugin"): _mock_mixer_set_slot_plugin,
    ("channels", "list_channels"): _mock_channels_list,
    ("channels", "list"): _mock_channels_list,
    ("channels", "get_channel"): _mock_channels_get_channel,
    ("channels", "get_info"): _mock_channels_get_channel,
    ("channels", "get_selected"): _mock_channels_get_selected,
    ("channels", "get_target_fx_track"): _mock_channels_get_target_fx_track,
    ("channels", "select_channel"): _mock_channels_select_channel,
    ("channels", "update_channel"): _mock_channels_update_channel,
    ("channels", "set_volume"): _mock_channels_set_volume,
    ("channels", "set_pan"): _mock_channels_set_pan,
    ("channels", "mute"): _mock_channels_mute,
    ("channels", "solo"): _mock_channels_solo,
    ("channels", "route_to_mixer"): _mock_channels_route_to_mixer,
    ("channels", "get_step_sequence"): _mock_channels_get_step_sequence,
    ("channels", "set_step_sequence"): _mock_channels_set_step_sequence,
    ("channels", "trigger_note"): _mock_channels_trigger_note,
    ("channels", "set_pitch"): _mock_channels_set_pitch,
    ("channels", "duplicate"): _mock_channels_duplicate,
    ("channels", "get_color"): _mock_channels_get_color,
    ("channels", "set_color"): _mock_channels_set_color,
    ("channels", "get_volume"): _mock_channels_get_volume,
    ("channels", "get_pan"): _mock_channels_get_pan,
    ("channels", "get_type"): _mock_channels_get_type,
    ("channels", "get_midi_in_port"): _mock_channels_get_midi_in_port,
    ("channels", "get_grid_bit"): _mock_channels_get_grid_bit,
    ("channels", "set_grid_bit"): _mock_channels_set_grid_bit,
    ("channels", "quick_quantize"): _mock_channels_quick_quantize,
    ("channels", "load_sample"): _mock_channels_load_sample,
    ("patterns", "list_patterns"): _mock_patterns_list,
    ("patterns", "list"): _mock_patterns_list,
    ("patterns", "select_pattern"): _mock_patterns_select,
    ("patterns", "select"): _mock_patterns_select,
    ("patterns", "create_pattern"): _mock_patterns_create,
    ("patterns", "create"): _mock_patterns_create,
    ("patterns", "rename_pattern"): _mock_patterns_rename,
    ("patterns", "rename"): _mock_patterns_rename,
    ("patterns", "set_length"): _mock_patterns_set_length,
    ("patterns", "get_color"): _mock_patterns_get_color,
    ("patterns", "set_color"): _mock_patterns_set_color,
    ("patterns", "clone"): _mock_patterns_clone,
    ("patterns", "jump_to"): _mock_patterns_jump_to,
    ("patterns", "is_default"): _mock_patterns_is_default,
    ("playlist", "list_tracks"): _mock_playlist_list_tracks,
    ("playlist", "get_track"): _mock_playlist_get_track,
    ("playlist", "get_track_info"): _mock_playlist_get_track,
    ("playlist", "update_track"): _mock_playlist_update_track,
    ("playlist", "set_track_name"): _mock_playlist_update_track,
    ("playlist", "get_track_color"): _mock_playlist_get_track_color,
    ("playlist", "set_track_color"): _mock_playlist_set_track_color,
    ("playlist", "mute_track"): _mock_playlist_mute_track,
    ("playlist", "solo_track"): _mock_playlist_solo_track,
    ("playlist", "select_track"): _mock_playlist_select_track,
    ("playlist", "get_track_activity"): _mock_playlist_get_track_activity,
    ("playlist", "list_clips"): _mock_playlist_list_clips,
    ("playlist", "place_clip"): _mock_playlist_place_clip,
    ("playlist", "move_clip"): _mock_playlist_move_clip,
    ("playlist", "delete_clip"): _mock_playlist_delete_clip,
    ("playlist", "list_markers"): _mock_playlist_list_markers,
    ("playlist", "create_marker"): _mock_playlist_create_marker,
    ("playlist", "update_marker"): _mock_playlist_update_marker,
    ("playlist", "delete_marker"): _mock_playlist_delete_marker,
    ("playlist", "get_arrangement"): _mock_playlist_get_arrangement,
    ("piano-roll", "get_state"): _mock_piano_roll_get_state,
    ("piano-roll", "send_notes"): _mock_piano_roll_send_notes,
    ("piano-roll", "delete_notes"): _mock_piano_roll_delete_notes,
    ("piano-roll", "clear"): _mock_piano_roll_clear,
    ("piano-roll", "quantize"): _mock_piano_roll_quantize,
    ("piano-roll", "transpose"): _mock_piano_roll_transpose,
    ("piano-roll", "humanize"): _mock_piano_roll_humanize,
    ("piano-roll", "generate_chords"): _mock_piano_roll_generate_chords,
    ("piano-roll", "generate_melody"): _mock_piano_roll_generate_melody,
    ("piano-roll", "generate_bass"): _mock_piano_roll_generate_bass,
    ("plugins", "list_plugins"): _mock_plugins_list_plugins,
    ("plugins", "list_params"): _mock_plugins_get_parameters,
    ("plugins", "get_parameters"): _mock_plugins_get_parameters,
    ("plugins", "get_parameter"): _mock_plugins_get_parameter,
    ("plugins", "get_param_value"): _mock_plugins_get_parameter,
    ("plugins", "get_parameter_name"): _mock_plugins_get_parameter_name,
    ("plugins", "set_parameter"): _mock_plugins_set_parameter,
    ("plugins", "set_param_value"): _mock_plugins_set_parameter,
    ("plugins", "next_preset"): _mock_plugins_next_preset,
    ("plugins", "prev_preset"): _mock_plugins_prev_preset,
    ("plugins", "previous_preset"): _mock_plugins_prev_preset,
    ("plugins", "get_param_value_string"): _mock_plugins_get_param_value_string,
    ("plugins", "get_color"): _mock_plugins_get_color,
    ("plugins", "get_pad_info"): _mock_plugins_get_pad_info,
    ("plugins", "get_preset_name"): _mock_plugins_get_preset_name,
    ("plugins", "load_preset_by_name"): _mock_plugins_load_preset_by_name,
    ("plugins", "is_valid"): _mock_plugins_is_valid,
    ("plugins", "get_name"): _mock_plugins_get_name,
    ("plugins", "get_parameter_count"): _mock_plugins_get_parameter_count,
    ("plugins", "get_preset_count"): _mock_plugins_get_preset_count,
    ("plugins", "show_window"): _mock_plugins_show_window,
    ("plugins", "load"): _mock_plugins_load,
    ("plugins", "replace"): _mock_plugins_replace,
    ("plugins", "inventory_scan"): _mock_plugins_inventory_scan,
    ("plugins", "list_profiles"): _mock_plugins_list_profiles,
    ("plugins", "get_profile"): _mock_plugins_get_profile,
    ("plugins", "resolve_profile"): _mock_plugins_resolve_profile,
    ("plugins", "probe_instance"): _mock_plugins_probe_instance,
    ("plugins", "enumerate_parameters"): _mock_plugins_enumerate_parameters,
    ("plugins", "probe_loadability"): _mock_plugins_probe_loadability,
    ("plugins", "generate_raw_profile"): _mock_plugins_generate_raw_profile,
    ("plugins", "learn_parameter"): _mock_plugins_learn_parameter,
    ("plugins", "validate_profile"): _mock_plugins_validate_profile,
    ("plugins", "verify_profile_controls"): _mock_plugins_verify_profile_controls,
    ("plugins", "write_calibration_overlay"): _mock_plugins_write_calibration_overlay,
    ("plugins", "get_mapped_parameter"): _mock_plugins_get_mapped_parameter,
    ("plugins", "set_mapped_parameter"): _mock_plugins_set_mapped_parameter,
    ("plugins", "load_profile_preset"): _mock_plugins_load_profile_preset,
    ("plugins", "list_local_presets"): _mock_plugins_list_local_presets,
    ("plugins", "reconcile_inventory"): _mock_plugins_reconcile_inventory,
    ("plugins", "priority_support_audit"): _mock_plugins_priority_support_audit,
    ("plugins", "export_support_matrix"): _mock_plugins_export_support_matrix,
    ("ui", "get_visibility"): _mock_ui_get_visibility,
    ("ui", "get_visible"): _mock_ui_get_visibility,
    ("ui", "show_window"): _mock_ui_show_window,
    ("ui", "hide_window"): _mock_ui_hide_window,
    ("ui", "get_focused"): _mock_ui_get_focused,
    ("ui", "set_focused"): _mock_ui_set_focused,
    ("ui", "get_focused_form_caption"): _mock_ui_get_focused_form_caption,
    ("ui", "get_focused_plugin_name"): _mock_ui_get_focused_plugin_name,
    ("ui", "scroll_window"): _mock_ui_scroll_window,
    ("ui", "next_window"): _mock_ui_next_window,
    ("ui", "get_snap_mode"): _mock_ui_get_snap_mode,
    ("ui", "set_snap_mode"): _mock_ui_set_snap_mode,
    ("ui", "get_hint_msg"): _mock_ui_get_hint_msg,
    ("ui", "set_hint_msg"): _mock_ui_set_hint_msg,
    ("ui", "get_step_edit_mode"): _mock_ui_get_step_edit_mode,
    ("general", "get_version"): _mock_general_get_version,
    ("general", "get_project_title"): _mock_general_get_project_title,
    ("general", "save_project"): _mock_general_save_project,
    ("general", "undo"): _mock_general_undo,
    ("general", "redo"): _mock_general_redo,
    ("general", "get_changed_flag"): _mock_general_get_changed_flag,
    ("general", "get_rec_ppq"): _mock_general_get_rec_ppq,
    ("general", "get_metronome"): _mock_general_get_metronome,
    ("general", "get_precount"): _mock_general_get_precount,
    ("general", "save_undo"): _mock_general_save_undo,
    ("general", "restore_undo"): _mock_general_restore_undo,
    ("general", "get_undo_history_pos"): _mock_general_get_undo_history_pos,
    ("general", "get_undo_history_count"): _mock_general_get_undo_history_count,
    ("general", "new_project"): _mock_general_new_project,
    ("general", "close_project"): _mock_general_close_project,
    ("general", "get_project_path"): _mock_general_get_project_path,
    ("general", "get_project_state"): _mock_general_get_project_state,
    ("general", "open_project"): _mock_general_open_project,
    ("general", "save_project_as"): _mock_general_save_project_as,
    ("render", "export"): _mock_render_export,
    ("render", "get_job"): _mock_render_get_job,
    ("render", "cancel_job"): _mock_render_cancel_job,
    ("audio", "analyze"): _mock_audio_analyze,
    ("audio", "get_analysis"): _mock_audio_get_analysis,
    ("audio", "cancel_analysis"): _mock_audio_cancel_analysis,
    ("device", "is_assigned"): _mock_device_is_assigned,
    ("device", "get_name"): _mock_device_get_name,
    ("device", "get_port_number"): _mock_device_get_port_number,
    ("device", "midi_out_msg"): _mock_device_midi_out_msg,
    ("device", "midi_out_sysex"): _mock_device_midi_out_sysex,
    ("arrangement", "get_current_time"): _mock_arrangement_get_current_time,
    ("arrangement", "get_time_hint"): _mock_arrangement_get_time_hint,
    ("arrangement", "get_selection_start"): _mock_arrangement_get_selection_start,
    ("arrangement", "get_selection_end"): _mock_arrangement_get_selection_end,
    ("arrangement", "jump_to_marker"): _mock_arrangement_jump_to_marker,
    ("automation", "list_clips"): _mock_automation_list_clips,
    ("automation", "get_clip"): _mock_automation_get_clip,
    ("automation", "create_clip"): _mock_automation_create_clip,
    ("automation", "delete_clip"): _mock_automation_delete_clip,
    ("automation", "write_points"): _mock_automation_write_points,
    ("automation", "read_points"): _mock_automation_read_points,
    ("automation", "link_to_parameter"): _mock_automation_link_to_parameter,
}


def _default_mock_result(
    payload: dict[str, object],
    rollback_class: RollbackClass | None,
) -> dict[str, object]:
    if rollback_class is not None:
        return {"acknowledged": True, "payload": payload, "rollback_class": rollback_class}
    return {"acknowledged": True, "payload": payload}


def mock_result(
    domain: str,
    operation: str,
    payload: dict[str, object],
    rollback_class: RollbackClass | None,
) -> dict[str, object]:
    """Return a deterministic mock result for *domain*.*operation*."""
    if operation == "noop":
        return _mock_noop(payload)

    handler = _MOCK_DISPATCH.get((domain, operation))
    if handler is not None:
        return handler(payload)

    return _default_mock_result(payload, rollback_class)
