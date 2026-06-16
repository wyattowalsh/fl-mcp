"""Bridge client for an already-selected FL Studio MCP controller script."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from pydantic import ValidationError

from fl_mcp.bridge.bundle import _active_user_data_dir
from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse

SELECTED_CONTROLLER_DIR_ENV = "FL_MCP_SELECTED_CONTROLLER_DIR"
POLL_INTERVAL_ENV = "FL_MCP_SELECTED_CONTROLLER_POLL_SECONDS"
DEFAULT_POLL_INTERVAL_SECONDS = 0.05
DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS = 5.0
LOCK_FILE_NAME = ".mcp_command.lock"


class _SelectedControllerLock:
    def __init__(self, bridge_dir: Path, *, deadline: float, poll_interval_seconds: float) -> None:
        self._path = bridge_dir / LOCK_FILE_NAME
        self._deadline = deadline
        self._poll_interval_seconds = poll_interval_seconds
        self._acquired = False

    def acquire(self) -> bool:
        while time.monotonic() < self._deadline:
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                time.sleep(self._poll_interval_seconds)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()} created_at={time.time()}\n")
            self._acquired = True
            return True
        return False

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
        finally:
            self._acquired = False


def selected_controller_dir_from_environment() -> Path:
    """Return the command directory for the selected FLStudioMCP controller."""

    configured = os.getenv(SELECTED_CONTROLLER_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    return _active_user_data_dir(Path.home()) / "Settings/Hardware/FLStudioMCP"


def _poll_interval_from_environment() -> float:
    raw = os.getenv(POLL_INTERVAL_ENV)
    if raw is None:
        return DEFAULT_POLL_INTERVAL_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_POLL_INTERVAL_SECONDS
    return value if value > 0 else DEFAULT_POLL_INTERVAL_SECONDS


def _response(
    request: BridgeLiveRequest,
    *,
    success: bool,
    message: str,
    error_code: str | None = None,
    result: dict[str, object] | None = None,
    execution_id: str | None = None,
) -> BridgeLiveResponse:
    return BridgeLiveResponse(
        success=success,
        message=message,
        error_code=error_code,
        execution_id=execution_id,
        provider=request.provider or "flapi-live",
        result=result or {},
    )


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)
    os.utime(path, None)


def _read_json_object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Selected controller response must be a JSON object.")
    return {str(key): value for key, value in decoded.items()}


def _int_payload(payload: dict[str, object], *names: str, default: int) -> int:
    for name in names:
        value = payload.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                continue
    return default


def _float_payload(payload: dict[str, object], *names: str, default: float) -> float:
    for name in names:
        value = payload.get(name)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return default


def _str_payload(payload: dict[str, object], *names: str, default: str) -> str:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return str(value)
    return default


def _bool_payload(payload: dict[str, object], *names: str, default: bool | None) -> bool | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if value == -1:
                return None
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            if normalized in {"toggle", "-1"}:
                return None
    return default


def _rgb_payload(payload: dict[str, object]) -> dict[str, int]:
    raw_color = payload.get("color")
    if isinstance(raw_color, str):
        try:
            raw_color = int(raw_color.removeprefix("#"), 16)
        except ValueError:
            raw_color = None
    if isinstance(raw_color, int):
        value = max(0, min(raw_color, 0xFFFFFF))
        return {
            "r": (value >> 16) & 0xFF,
            "g": (value >> 8) & 0xFF,
            "b": value & 0xFF,
        }
    return {
        "r": _int_payload(payload, "r", "red", default=0),
        "g": _int_payload(payload, "g", "green", default=0),
        "b": _int_payload(payload, "b", "blue", default=0),
    }


def _track_index(payload: dict[str, object]) -> int:
    return _int_payload(payload, "track", "track_index", "index", default=0)


def _channel_index(payload: dict[str, object]) -> int:
    return _int_payload(payload, "channel", "channel_index", "index", default=0)


def _plugin_slot(payload: dict[str, object]) -> int:
    return _int_payload(payload, "slot_index", "plugin_slot", default=-1)


def _step_sequence_pattern(payload: dict[str, object]) -> list[bool]:
    raw_pattern = payload.get("pattern")
    if isinstance(raw_pattern, list):
        return [bool(value) for value in raw_pattern]

    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        return []

    active_steps: set[int] = set()
    for step in raw_steps:
        if isinstance(step, int) and step >= 0:
            active_steps.add(step)
        elif isinstance(step, str):
            try:
                parsed = int(step)
            except ValueError:
                continue
            if parsed >= 0:
                active_steps.add(parsed)

    length = max(16, max(active_steps, default=-1) + 1)
    return [index in active_steps for index in range(length)]


def _plugin_param_index(payload: dict[str, object]) -> int | None:
    for name in ("param_index", "parameter_index"):
        value = payload.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass

    parameter = payload.get("parameter")
    if isinstance(parameter, int):
        return parameter
    if isinstance(parameter, str):
        normalized = parameter.strip()
        if normalized.isdigit():
            return int(normalized)

    return None


def _selected_controller_commands(
    request: BridgeLiveRequest,
) -> list[dict[str, object]] | None:
    payload = request.payload
    if request.domain == "transport" and request.operation in {
        "get_state",
        "get_playback_state",
        "get_song_position",
        "get_tempo",
    }:
        return [{"action": "transport.getStatus", "params": {}}]
    if request.domain == "transport" and request.operation in {"pause", "play"}:
        return [{"action": "transport.start", "params": {}}]
    if request.domain == "transport" and request.operation == "stop":
        return [{"action": "transport.stop", "params": {}}]
    if request.domain == "transport" and request.operation == "record":
        return [{"action": "transport.record", "params": {}}]
    if request.domain == "transport" and request.operation == "set_tempo":
        return [
            {
                "action": "transport.setTempo",
                "params": {"tempo": _float_payload(payload, "tempo", "bpm", default=120.0)},
            }
        ]
    if request.domain == "transport" and request.operation == "set_song_position":
        return [
            {
                "action": "transport.setPosition",
                "params": {
                    "position": _float_payload(payload, "position", "position_beats", default=0.0),
                    "mode": _int_payload(payload, "mode", default=2),
                },
            }
        ]
    if request.domain == "transport" and request.operation == "get_length":
        return [{"action": "transport.getLength", "params": {}}]
    if request.domain == "transport" and request.operation == "set_loop_mode":
        return [
            {
                "action": "transport.setLoopMode",
                "params": {"mode": _str_payload(payload, "mode", default="pattern")},
            }
        ]
    if request.domain == "transport" and request.operation == "set_playback_speed":
        return [
            {
                "action": "transport.setPlaybackSpeed",
                "params": {"speed": _float_payload(payload, "speed", default=1.0)},
            }
        ]
    if request.domain == "mixer" and request.operation in {
        "get_track",
        "get_track_info",
        "get_track_pan",
        "get_track_volume",
        "get_track_color",
        "is_track_armed",
    }:
        return [
            {
                "action": "mixer.getTrackInfo",
                "params": {"track": _track_index(payload)},
            }
        ]
    if request.domain == "mixer" and request.operation == "get_track_count":
        return [{"action": "mixer.getTrackCount", "params": {}}]
    if request.domain == "mixer" and request.operation == "list_tracks":
        return [
            {
                "action": "mixer.getAllTracks",
                "params": {"include_empty": bool(payload.get("include_empty", True))},
            }
        ]
    if request.domain == "mixer" and request.operation in {"set_pan", "set_track_pan"}:
        return [
            {
                "action": "mixer.setTrackPan",
                "params": {
                    "track": _track_index(payload),
                    "pan": _float_payload(payload, "pan", default=0.0),
                },
            }
        ]
    if request.domain == "mixer" and request.operation in {"set_volume", "set_track_volume"}:
        return [
            {
                "action": "mixer.setTrackVolume",
                "params": {
                    "track": _track_index(payload),
                    "volume": _float_payload(payload, "volume", default=0.8),
                },
            }
        ]
    if request.domain == "mixer" and request.operation == "set_track_color":
        return [
            {
                "action": "mixer.setTrackColor",
                "params": {"track": _track_index(payload), **_rgb_payload(payload)},
            }
        ]
    if request.domain == "mixer" and request.operation == "set_stereo_separation":
        return [
            {
                "action": "mixer.setStereoSep",
                "params": {
                    "track": _track_index(payload),
                    "separation": _float_payload(
                        payload,
                        "stereo_separation",
                        "separation",
                        default=0.0,
                    ),
                },
            }
        ]
    if request.domain == "mixer" and request.operation == "mute_track":
        return [
            {
                "action": "mixer.muteTrack",
                "params": {
                    "track": _track_index(payload),
                    "muted": _bool_payload(payload, "muted", "value", default=None),
                },
            }
        ]
    if request.domain == "mixer" and request.operation == "solo_track":
        return [
            {
                "action": "mixer.soloTrack",
                "params": {
                    "track": _track_index(payload),
                    "solo": _bool_payload(payload, "solo", "value", default=None),
                },
            }
        ]
    if request.domain == "mixer" and request.operation == "arm_track":
        return [
            {
                "action": "mixer.armTrack",
                "params": {"track": _track_index(payload)},
            }
        ]
    if request.domain == "mixer" and request.operation == "update_track":
        track = _track_index(payload)
        commands: list[dict[str, object]] = []
        if payload.get("name") is not None:
            commands.append(
                {
                    "action": "mixer.setTrackName",
                    "params": {"track": track, "name": _str_payload(payload, "name", default="")},
                }
            )
        if payload.get("color") is not None:
            commands.append(
                {
                    "action": "mixer.setTrackColor",
                    "params": {"track": track, **_rgb_payload(payload)},
                }
            )
        if payload.get("volume") is not None:
            commands.append(
                {
                    "action": "mixer.setTrackVolume",
                    "params": {
                        "track": track,
                        "volume": _float_payload(payload, "volume", default=0.8),
                    },
                }
            )
        if payload.get("pan") is not None:
            commands.append(
                {
                    "action": "mixer.setTrackPan",
                    "params": {"track": track, "pan": _float_payload(payload, "pan", default=0.0)},
                }
            )
        if payload.get("muted") is not None:
            commands.append(
                {
                    "action": "mixer.muteTrack",
                    "params": {
                        "track": track,
                        "muted": _bool_payload(payload, "muted", default=None),
                    },
                }
            )
        if payload.get("solo") is not None:
            commands.append(
                {
                    "action": "mixer.soloTrack",
                    "params": {
                        "track": track,
                        "solo": _bool_payload(payload, "solo", default=None),
                    },
                }
            )
        if payload.get("armed") is not None:
            commands.append({"action": "mixer.armTrack", "params": {"track": track}})
        return commands or None
    if request.domain == "channels" and request.operation in {
        "list",
        "list_channels",
    }:
        return [{"action": "channels.getAll", "params": {}}]
    if request.domain == "channels" and request.operation == "get_selected":
        return [{"action": "channels.getSelected", "params": {}}]
    if request.domain == "channels" and request.operation in {
        "get_channel",
        "get_info",
        "get_target_fx_track",
        "get_color",
        "get_volume",
        "get_pan",
        "get_type",
    }:
        return [{"action": "channels.getInfo", "params": {"index": _channel_index(payload)}}]
    if request.domain == "channels" and request.operation == "select_channel":
        action = (
            "channels.selectOne" if bool(payload.get("exclusive", False)) else "channels.select"
        )
        params: dict[str, object] = {"index": _channel_index(payload)}
        if action == "channels.select":
            params["select"] = _bool_payload(payload, "select", default=True)
        return [{"action": action, "params": params}]
    if request.domain == "channels" and request.operation == "trigger_note":
        return [
            {
                "action": "channels.triggerNote",
                "params": {
                    "channel": _channel_index(payload),
                    "note": _int_payload(payload, "note", default=60),
                    "velocity": _int_payload(payload, "velocity", default=100),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "set_volume":
        return [
            {
                "action": "channels.setVolume",
                "params": {
                    "index": _channel_index(payload),
                    "volume": _float_payload(payload, "volume", default=0.8),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "set_pan":
        return [
            {
                "action": "channels.setPan",
                "params": {
                    "index": _channel_index(payload),
                    "pan": _float_payload(payload, "pan", default=0.0),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "mute":
        return [
            {
                "action": "channels.mute",
                "params": {
                    "index": _channel_index(payload),
                    "muted": _bool_payload(payload, "muted", "value", default=None),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "solo":
        return [
            {
                "action": "channels.solo",
                "params": {
                    "index": _channel_index(payload),
                    "solo": _bool_payload(payload, "solo", "value", default=None),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "set_color":
        return [
            {
                "action": "channels.setColor",
                "params": {"index": _channel_index(payload), **_rgb_payload(payload)},
            }
        ]
    if request.domain == "channels" and request.operation == "route_to_mixer":
        return [
            {
                "action": "channels.routeToMixer",
                "params": {
                    "channel_index": _channel_index(payload),
                    "mixer_track": _int_payload(
                        payload,
                        "mixer_track",
                        "mixer_track_index",
                        default=0,
                    ),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "update_channel":
        index = _channel_index(payload)
        commands: list[dict[str, object]] = []
        if payload.get("name") is not None:
            commands.append(
                {
                    "action": "channels.setName",
                    "params": {"index": index, "name": _str_payload(payload, "name", default="")},
                }
            )
        if payload.get("color") is not None:
            commands.append(
                {
                    "action": "channels.setColor",
                    "params": {"index": index, **_rgb_payload(payload)},
                }
            )
        if payload.get("volume") is not None:
            commands.append(
                {
                    "action": "channels.setVolume",
                    "params": {
                        "index": index,
                        "volume": _float_payload(payload, "volume", default=0.8),
                    },
                }
            )
        if payload.get("pan") is not None:
            commands.append(
                {
                    "action": "channels.setPan",
                    "params": {"index": index, "pan": _float_payload(payload, "pan", default=0.0)},
                }
            )
        if payload.get("muted") is not None:
            commands.append(
                {
                    "action": "channels.mute",
                    "params": {
                        "index": index,
                        "muted": _bool_payload(payload, "muted", default=None),
                    },
                }
            )
        if payload.get("solo") is not None:
            commands.append(
                {
                    "action": "channels.solo",
                    "params": {
                        "index": index,
                        "solo": _bool_payload(payload, "solo", default=None),
                    },
                }
            )
        return commands or None
    if request.domain == "channels" and request.operation == "get_grid_bit":
        return [
            {
                "action": "channels.getGridBit",
                "params": {
                    "channel": _channel_index(payload),
                    "position": _int_payload(payload, "position", default=0),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "set_grid_bit":
        return [
            {
                "action": "channels.setGridBit",
                "params": {
                    "channel": _channel_index(payload),
                    "position": _int_payload(payload, "position", default=0),
                    "value": bool(payload.get("value", False)),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "get_step_sequence":
        return [
            {
                "action": "channels.getStepSequence",
                "params": {
                    "channel": _channel_index(payload),
                    "steps": _int_payload(payload, "step_count", "steps", default=16),
                },
            }
        ]
    if request.domain == "channels" and request.operation == "set_step_sequence":
        return [
            {
                "action": "channels.setStepSequence",
                "params": {
                    "channel": _channel_index(payload),
                    "pattern": _step_sequence_pattern(payload),
                },
            }
        ]
    if request.domain == "plugins" and request.operation == "is_valid":
        return [
            {
                "action": "plugins.isValid",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation == "get_name":
        return [
            {
                "action": "plugins.getName",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation in {"get_parameters", "list_params"}:
        return [
            {
                "action": "plugins.getParams",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation in {"get_parameter_count"}:
        return [
            {
                "action": "plugins.getParamCount",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation in {"get_parameter_name"}:
        param_index = _plugin_param_index(payload)
        if param_index is None:
            return None
        return [
            {
                "action": "plugins.getParamName",
                "params": {
                    "plugin_index": _channel_index(payload),
                    "slot_index": _plugin_slot(payload),
                    "param_index": param_index,
                },
            }
        ]
    if request.domain == "plugins" and request.operation in {
        "get_parameter",
        "get_param_value",
        "get_param_value_string",
    }:
        param_index = _plugin_param_index(payload)
        if param_index is None:
            return None
        return [
            {
                "action": "plugins.getParamValue",
                "params": {
                    "plugin_index": _channel_index(payload),
                    "slot_index": _plugin_slot(payload),
                    "param_index": param_index,
                },
            }
        ]
    if request.domain == "plugins" and request.operation in {"set_parameter", "set_param_value"}:
        param_index = _plugin_param_index(payload)
        if param_index is None:
            return None
        return [
            {
                "action": "plugins.setParamValue",
                "params": {
                    "plugin_index": _channel_index(payload),
                    "slot_index": _plugin_slot(payload),
                    "param_index": param_index,
                    "value": _float_payload(payload, "value", default=0.0),
                },
            }
        ]
    if request.domain == "plugins" and request.operation == "get_preset_count":
        return [
            {
                "action": "plugins.getPresetCount",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation == "next_preset":
        return [
            {
                "action": "plugins.nextPreset",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation in {"prev_preset", "previous_preset"}:
        return [
            {
                "action": "plugins.prevPreset",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    if request.domain == "plugins" and request.operation == "get_color":
        return [
            {
                "action": "plugins.getColor",
                "params": {"index": _channel_index(payload), "slot_index": _plugin_slot(payload)},
            }
        ]
    return None


def selected_controller_supports(domain: str, operation: str) -> bool:
    """Return whether the selected-controller adapter can translate an operation."""

    payload: dict[str, object] = {}
    if domain == "plugins" and operation in {
        "get_parameter",
        "get_param_value",
        "get_param_value_string",
        "get_parameter_name",
        "set_parameter",
        "set_param_value",
    }:
        payload["param_index"] = 0
    request = BridgeLiveRequest(
        domain=domain,
        operation=operation,
        provider="flapi-live",
        payload=payload,
    )
    return _selected_controller_commands(request) is not None


def _normalize_success_response(
    request: BridgeLiveRequest,
    decoded: dict[str, object],
    *,
    execution_id: str,
) -> BridgeLiveResponse:
    error = decoded.get("error")
    if isinstance(error, str) and error:
        return _response(
            request,
            success=False,
            error_code="selected_controller_error",
            message=error,
            execution_id=execution_id,
            result=decoded,
        )
    success = decoded.get("success")
    if success is False:
        return _response(
            request,
            success=False,
            error_code="selected_controller_error",
            message="Selected FL Studio controller reported failure.",
            execution_id=execution_id,
            result=decoded,
        )
    result = {key: value for key, value in decoded.items() if key != "success"}
    return _response(
        request,
        success=True,
        message=f"Selected FL Studio controller executed {request.domain}.{request.operation}.",
        execution_id=execution_id,
        result=result,
    )


def _normalize_sequence_response(
    request: BridgeLiveRequest,
    decoded_items: list[dict[str, object]],
    *,
    execution_id: str,
) -> BridgeLiveResponse:
    if not decoded_items:
        return _response(
            request,
            success=False,
            error_code="selected_controller_error",
            message="Selected FL Studio controller did not return a response.",
            execution_id=execution_id,
        )
    if len(decoded_items) == 1:
        return _normalize_success_response(request, decoded_items[0], execution_id=execution_id)

    command_results: list[dict[str, object]] = []
    for decoded in decoded_items:
        error = decoded.get("error")
        if isinstance(error, str) and error:
            return _response(
                request,
                success=False,
                error_code="selected_controller_error",
                message=error,
                execution_id=execution_id,
                result={"commands": command_results, "failed_response": decoded},
            )
        if decoded.get("success") is False:
            return _response(
                request,
                success=False,
                error_code="selected_controller_error",
                message="Selected FL Studio controller reported failure.",
                execution_id=execution_id,
                result={"commands": command_results, "failed_response": decoded},
            )
        command_results.append({key: value for key, value in decoded.items() if key != "success"})

    result = dict(command_results[-1])
    result["commands"] = command_results
    return _response(
        request,
        success=True,
        message=f"Selected FL Studio controller executed {request.domain}.{request.operation}.",
        execution_id=execution_id,
        result=result,
    )


def _execute_command_file_round_trip(
    *,
    command_path: Path,
    response_path: Path,
    command: dict[str, object],
    deadline: float,
    poll_interval: float,
) -> tuple[dict[str, object] | None, str | None]:
    response_mtime = response_path.stat().st_mtime_ns if response_path.exists() else 0
    _write_json_atomic(command_path, command)

    last_error: str | None = None
    while time.monotonic() < deadline:
        if response_path.exists() and response_path.stat().st_mtime_ns > response_mtime:
            try:
                return _read_json_object(response_path), None
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
        time.sleep(poll_interval)
    return None, last_error


def run_selected_controller_bridge(
    request: BridgeLiveRequest,
    *,
    controller_dir: Path | None = None,
    timeout_seconds: float = DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
    poll_interval_seconds: float | None = None,
) -> BridgeLiveResponse:
    """Execute one request through an already-selected FLStudioMCP script."""

    commands = _selected_controller_commands(request)
    if commands is None:
        return _response(
            request,
            success=False,
            error_code="unsupported_operation",
            message=(
                "Selected-controller adapter does not implement "
                f"{request.domain}.{request.operation}."
            ),
        )

    bridge_dir = controller_dir or selected_controller_dir_from_environment()
    command_path = bridge_dir / "mcp_command.json"
    response_path = bridge_dir / "mcp_response.json"
    if not bridge_dir.exists():
        return _response(
            request,
            success=False,
            error_code="selected_controller_missing",
            message=f"Selected FL Studio controller directory does not exist: {bridge_dir}.",
            result={"controller_dir": str(bridge_dir)},
        )

    execution_id = f"selected-controller-{uuid.uuid4().hex}"
    poll_interval = poll_interval_seconds or _poll_interval_from_environment()
    deadline = time.monotonic() + timeout_seconds
    lock = _SelectedControllerLock(
        bridge_dir,
        deadline=deadline,
        poll_interval_seconds=poll_interval,
    )
    try:
        acquired = lock.acquire()
    except OSError as exc:
        return _response(
            request,
            success=False,
            error_code="selected_controller_lock_error",
            message=f"Could not acquire selected-controller lock: {exc}.",
            execution_id=execution_id,
            result={"controller_dir": str(bridge_dir)},
        )
    if not acquired:
        return _response(
            request,
            success=False,
            error_code="selected_controller_busy",
            message=(
                "Timed out waiting for another selected-controller request to finish. "
                f"Lock file: {bridge_dir / LOCK_FILE_NAME}."
            ),
            execution_id=execution_id,
            result={"controller_dir": str(bridge_dir)},
        )

    last_error: str | None = None
    try:
        decoded_items: list[dict[str, object]] = []
        for command in commands:
            decoded, last_error = _execute_command_file_round_trip(
                command_path=command_path,
                response_path=response_path,
                command=command,
                deadline=deadline,
                poll_interval=poll_interval,
            )
            if decoded is None:
                break
            decoded_items.append(decoded)
        if len(decoded_items) == len(commands):
            return _normalize_sequence_response(
                request,
                decoded_items,
                execution_id=execution_id,
            )

        return _response(
            request,
            success=False,
            error_code="selected_controller_timeout",
            message=(
                "Timed out waiting for selected FL Studio MCP controller response. "
                f"Ensure the selected controller script is polling {bridge_dir}."
            ),
            execution_id=execution_id,
            result={"controller_dir": str(bridge_dir), "last_error": last_error},
        )
    finally:
        lock.release()


class SelectedControllerClient:
    """Small convenience facade for the selected-controller compatibility bridge."""

    def __init__(
        self,
        *,
        controller_dir: Path | None = None,
        timeout_seconds: float = DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
        poll_interval_seconds: float | None = None,
        provider: str = "flapi-live",
    ) -> None:
        self._controller_dir = controller_dir
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._provider = provider

    def execute(
        self,
        domain: str,
        operation: str,
        payload: dict[str, object] | None = None,
    ) -> BridgeLiveResponse:
        request = BridgeLiveRequest(
            domain=domain,
            operation=operation,
            provider=self._provider,
            payload=payload or {},
        )
        return run_selected_controller_bridge(
            request,
            controller_dir=self._controller_dir,
            timeout_seconds=self._timeout_seconds,
            poll_interval_seconds=self._poll_interval_seconds,
        )

    def read_transport(self) -> BridgeLiveResponse:
        """Read transport state through the selected FL Studio controller."""

        return self.execute("transport", "get_state")

    def set_transport_tempo(self, tempo: float) -> BridgeLiveResponse:
        """Set the transport tempo through the selected FL Studio controller."""

        return self.execute("transport", "set_tempo", {"tempo": tempo})


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by ``FL_MCP_FL_STUDIO_BRIDGE_CMD`` diagnostics."""

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        request = BridgeLiveRequest(domain="controller", operation="parse", provider="flapi-live")
        response = _response(
            request,
            success=False,
            error_code="invalid_request",
            message="Expected exactly one JSON request argument.",
        )
        print(json.dumps(response.model_dump(mode="json"), sort_keys=True))
        return 2

    try:
        request = BridgeLiveRequest.model_validate_json(args[0])
        response = run_selected_controller_bridge(request)
    except (ValidationError, ValueError) as exc:
        request = BridgeLiveRequest(domain="controller", operation="parse", provider="flapi-live")
        response = _response(
            request,
            success=False,
            error_code="invalid_request",
            message=str(exc),
        )
    print(json.dumps(response.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
