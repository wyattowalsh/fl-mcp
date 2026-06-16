"""Shipped live FL API operation surface for the default host-file bridge."""

from __future__ import annotations

LIVE_FLAPI_OPERATIONS: dict[str, tuple[str, ...]] = {
    "general": ("get_project_title", "get_version"),
    "transport": (
        "get_state",
        "get_tempo",
        "pause",
        "play",
        "set_tempo",
        "stop",
    ),
}

FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS: tuple[str, ...] = (
    "arrangement",
    "audio",
    "automation",
    "channels",
    "connection",
    "device",
    "general",
    "midi",
    "mixer",
    "patterns",
    "piano-roll",
    "playlist",
    "plugins",
    "render",
    "transport",
    "ui",
)
LIVE_FLAPI_SUPPORTED_DOMAINS: tuple[str, ...] = tuple(sorted(LIVE_FLAPI_OPERATIONS))
LIVE_FLAPI_TOOL_NAMES: tuple[str, ...] = (
    "general_get_project_title",
    "general_get_version",
    "transport_get_state",
    "transport_get_tempo",
    "transport_pause",
    "transport_play",
    "transport_set_tempo",
    "transport_stop",
)
SELECTED_CONTROLLER_COMPAT_TOOL_NAMES: tuple[str, ...] = (
    "channels_get_channel",
    "channels_get_color",
    "channels_get_grid_bit",
    "channels_get_pan",
    "channels_get_selected",
    "channels_get_step_sequence",
    "channels_get_target_fx_track",
    "channels_get_type",
    "channels_get_volume",
    "channels_list",
    "channels_mute",
    "channels_route_to_mixer",
    "channels_select_channel",
    "channels_set_color",
    "channels_set_grid_bit",
    "channels_set_pan",
    "channels_set_step_sequence",
    "channels_set_volume",
    "channels_solo",
    "channels_trigger_note",
    "channels_update_channel",
    "mixer_get_track",
    "mixer_get_track_color",
    "mixer_get_track_count",
    "mixer_get_track_pan",
    "mixer_get_track_volume",
    "mixer_is_track_armed",
    "mixer_list_tracks",
    "mixer_arm_track",
    "mixer_mute_track",
    "mixer_set_stereo_separation",
    "mixer_set_track_color",
    "mixer_set_track_pan",
    "mixer_set_track_volume",
    "mixer_solo_track",
    "mixer_update_track",
    "plugins_get_color",
    "plugins_get_name",
    "plugins_get_parameter_name",
    "plugins_get_param_value_string",
    "plugins_get_parameter",
    "plugins_get_parameter_count",
    "plugins_get_parameters",
    "plugins_get_preset_count",
    "plugins_is_valid",
    "plugins_next_preset",
    "plugins_prev_preset",
    "plugins_set_parameter",
    "transport_get_length",
    "transport_get_song_position",
    "transport_play",
    "transport_record",
    "transport_set_loop_mode",
    "transport_set_playback_speed",
    "transport_set_song_position",
    "transport_stop",
)

SELECTED_CONTROLLER_OPERATION_ALIASES: dict[tuple[str, str], str] = {
    ("channels", "list_channels"): "channels_list",
}


def live_flapi_supports(domain: str, operation: str) -> bool:
    """Return whether the default host-file bridge advertises this live operation."""

    return operation in LIVE_FLAPI_OPERATIONS.get(domain, ())


def selected_controller_supports(domain: str, operation: str) -> bool:
    """Return whether the selected-controller compatibility route advertises an operation."""

    capability = SELECTED_CONTROLLER_OPERATION_ALIASES.get(
        (domain, operation),
        f"{domain}_{operation}".replace("-", "_"),
    )
    return capability in SELECTED_CONTROLLER_COMPAT_TOOL_NAMES


def forced_live_flapi_supports(domain: str, operation: str) -> bool:
    """Return whether live mode should attempt this operation through flapi-live."""

    return domain in FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS and bool(operation)


def live_flapi_tool_names() -> list[str]:
    """Return canonical tool names backed by the default live FL API bridge."""

    return list(LIVE_FLAPI_TOOL_NAMES)


def flapi_provider_tool_names() -> list[str]:
    """Return canonical tool names reachable by shipped live FL provider paths."""

    return sorted({*LIVE_FLAPI_TOOL_NAMES, *SELECTED_CONTROLLER_COMPAT_TOOL_NAMES})
