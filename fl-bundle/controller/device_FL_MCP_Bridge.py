# name=FL MCP Bridge
# supportedDevices=FL MCP Bridge,IAC Driver Bus 1
"""FL Studio MIDI-script host bridge for fl-mcp.

Install this file as a custom MIDI script and select "FL MCP Bridge" in FL
Studio's MIDI Settings controller type menu. The script polls a local
request/response directory during OnIdle so MCP-side subprocess calls can execute
small, safe FL API operations inside the actual DAW Python host.
"""

from __future__ import annotations

import importlib
import json
import os
import stat
import time
import traceback

DEFAULT_BRIDGE_DIR_NAME = "bridge"
BRIDGE_DIR_ENV = "FL_MCP_FL_STUDIO_BRIDGE_DIR"
LOG_ENV = "FL_MCP_FL_STUDIO_BRIDGE_LOG"
STATUS_FILE = "status.json"
SCRIPT_LOG_FILE = "fl_mcp_bridge.log"
MIN_POLL_INTERVAL_SECONDS = 0.02
STATUS_HEARTBEAT_INTERVAL_SECONDS = 5.0
PROCESSED_REQUEST_TTL_SECONDS = 120.0
MAX_PROCESSED_REQUESTS = 512
_PRIVATE_DIR_MODE = 0o700

_FL_MODULE_NAMES = (
    "arrangement",
    "audio",
    "channels",
    "device",
    "general",
    "mixer",
    "patterns",
    "playlist",
    "plugins",
    "render",
    "transport",
    "ui",
)


def _import_fl_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


_FL_MODULES = {name: _import_fl_module(name) for name in _FL_MODULE_NAMES}

general = _FL_MODULES["general"]
mixer = _FL_MODULES["mixer"]
transport = _FL_MODULES["transport"]
ui = _FL_MODULES["ui"]

_last_poll_at = 0.0
_last_status_at = 0.0
_processed_request_count = 0
_last_bridge_error = None
_processed_request_paths = {}


def _script_dir() -> str:
    script_file = globals().get("__file__")
    if isinstance(script_file, str) and script_file:
        return os.path.dirname(os.path.abspath(script_file))
    return os.getcwd()


def _script_log_path() -> str:
    return os.path.join(_script_dir(), SCRIPT_LOG_FILE)


def _logging_enabled() -> bool:
    return os.getenv(LOG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _log(message: str) -> None:
    if not _logging_enabled():
        return
    try:
        with open(_script_log_path(), "a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def _bridge_dir() -> str:
    configured = os.getenv(BRIDGE_DIR_ENV)
    if not configured:
        configured = os.path.join(_script_dir(), DEFAULT_BRIDGE_DIR_NAME)
    return os.path.abspath(os.path.expanduser(configured))


def _default_bridge_dir() -> str:
    return os.path.abspath(os.path.join(_script_dir(), DEFAULT_BRIDGE_DIR_NAME))


def _using_default_bridge_dir(path: str) -> bool:
    return os.path.abspath(path) == _default_bridge_dir() and not os.getenv(BRIDGE_DIR_ENV)


def _ensure_private_bridge_dir(path: str) -> str:
    try:
        if os.path.exists(path):
            if os.path.islink(path):
                raise ValueError(f"Bridge directory must not be a symlink: {path}.")
            if not os.path.isdir(path):
                raise ValueError(f"Bridge path must be a directory: {path}.")
        else:
            os.makedirs(path, mode=_PRIVATE_DIR_MODE, exist_ok=True)

        if os.name == "posix":
            owner = getattr(os, "getuid", lambda: None)()
            current_stat = os.stat(path)
            if owner is not None and current_stat.st_uid != owner:
                raise ValueError(f"Bridge directory is not owned by the current user: {path}.")
            if stat.S_IMODE(current_stat.st_mode) != _PRIVATE_DIR_MODE:
                os.chmod(path, _PRIVATE_DIR_MODE)
                current_stat = os.stat(path)
            if stat.S_IMODE(current_stat.st_mode) != _PRIVATE_DIR_MODE:
                raise ValueError(f"Bridge directory permissions must be 0700: {path}.")
    except Exception as exc:
        if not _using_default_bridge_dir(path):
            raise
        _log(
            "strict bridge directory check skipped for script-local bridge "
            f"{path}: {type(exc).__name__}: {exc}"
        )

    return path


def _write_json_atomic(path: str, payload: dict) -> None:
    data = json.dumps(payload, sort_keys=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(data)
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass


def _request_from_envelope(envelope: dict) -> tuple[str, dict]:
    request_id = str(envelope.get("request_id", "manual"))
    request = envelope.get("request", envelope)
    if not isinstance(request, dict):
        request = {}
    return request_id, request


def _response(request: dict, *, success: bool, message: str, result=None, error_code=None) -> dict:
    domain = str(request.get("domain", "controller"))
    operation = str(request.get("operation", "parse"))
    provider = request.get("provider") or "flapi-live"
    return {
        "success": bool(success),
        "message": str(message),
        "error_code": error_code,
        "execution_id": f"fl-host-{domain}-{operation}",
        "provider": provider,
        "result": result or {},
    }


def _first_callable(module, names: tuple[str, ...]):
    if module is None:
        return None
    for name in names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    return None


def _fl_module(name: str):
    return globals().get(name) or _FL_MODULES.get(name)


_DOMAIN_MODULES = {
    "arrangement": ("arrangement", "playlist", "transport"),
    "audio": ("audio", "render", "general"),
    "automation": ("plugins", "mixer", "channels", "playlist"),
    "channels": ("channels",),
    "connection": ("device", "midi", "transport"),
    "device": ("device",),
    "general": ("general", "ui"),
    "midi": ("device",),
    "mixer": ("mixer",),
    "patterns": ("patterns",),
    "piano-roll": ("channels", "patterns"),
    "playlist": ("playlist",),
    "plugins": ("plugins",),
    "render": ("render", "general"),
    "transport": ("transport", "mixer"),
    "ui": ("ui",),
}

_EXPLICIT_CANDIDATES = {
    ("general", "get_version"): (("general", ("getVersion", "get_version")),),
    ("general", "get_project_title"): (("ui", ("getProgTitle",)),),
    ("transport", "get_tempo"): (
        ("transport", ("getCurrentTempo", "getTempo", "get_tempo")),
        ("mixer", ("getCurrentTempo",)),
    ),
    ("transport", "get_state"): (
        ("transport", ("getStatus", "getCurrentTempo", "getTempo", "isPlaying")),
        ("mixer", ("getCurrentTempo",)),
    ),
    ("transport", "set_tempo"): (
        ("transport", ("setCurrentTempo", "setTempo", "set_tempo")),
        ("mixer", ("setCurrentTempo",)),
    ),
    ("transport", "play"): (("transport", ("start", "play")),),
    ("transport", "pause"): (("transport", ("start", "pause")),),
    ("transport", "stop"): (("transport", ("stop",)),),
    ("transport", "record"): (("transport", ("record",)),),
    ("mixer", "set_track_volume"): (("mixer", ("setTrackVolume", "setVolume")),),
    ("mixer", "get_track_volume"): (("mixer", ("getTrackVolume", "getVolume")),),
    ("mixer", "set_track_pan"): (("mixer", ("setTrackPan", "setPan")),),
    ("mixer", "get_track_pan"): (("mixer", ("getTrackPan", "getPan")),),
    ("mixer", "set_track_color"): (("mixer", ("setTrackColor", "setColor")),),
    ("mixer", "get_track_color"): (("mixer", ("getTrackColor", "getColor")),),
    ("mixer", "mute_track"): (("mixer", ("muteTrack", "mute")),),
    ("mixer", "solo_track"): (("mixer", ("soloTrack", "solo")),),
    ("mixer", "arm_track"): (("mixer", ("armTrack", "arm")),),
    ("channels", "set_volume"): (("channels", ("setChannelVolume", "setVolume")),),
    ("channels", "get_volume"): (("channels", ("getChannelVolume", "getVolume")),),
    ("channels", "set_pan"): (("channels", ("setChannelPan", "setPan")),),
    ("channels", "get_pan"): (("channels", ("getChannelPan", "getPan")),),
    ("channels", "load_sample"): (("channels", ("loadSample", "load_sample")),),
    ("plugins", "set_parameter"): (("plugins", ("setParamValue", "setParameter")),),
    ("plugins", "get_parameter"): (("plugins", ("getParamValue", "getParameter")),),
    ("plugins", "get_parameter_name"): (("plugins", ("getParamName",)),),
    ("plugins", "get_param_value_string"): (("plugins", ("getParamValueString",)),),
    ("plugins", "load"): (("plugins", ("loadPlugin", "load")),),
    ("plugins", "replace"): (("plugins", ("replacePlugin", "replace")),),
    ("plugins", "next_preset"): (("plugins", ("nextPreset",)),),
    ("plugins", "prev_preset"): (("plugins", ("prevPreset", "previousPreset")),),
    ("render", "export"): (("render", ("render", "export")), ("general", ("render", "export"))),
}


def _camel(name: str) -> str:
    parts = [part for part in name.replace("-", "_").split("_") if part]
    if not parts:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _pascal(name: str) -> str:
    parts = [part for part in name.replace("-", "_").split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or name


def _candidate_names(operation: str) -> tuple[str, ...]:
    names = [
        operation,
        _camel(operation),
        _pascal(operation),
        operation.replace("_", ""),
    ]
    for prefix in ("get_", "set_", "create_", "delete_", "list_"):
        if operation.startswith(prefix):
            trimmed = operation.removeprefix(prefix)
            names.extend((_camel(trimmed), _pascal(trimmed), trimmed))
    seen = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return tuple(seen)


def _candidate_records(domain: str, operation: str) -> list[tuple[str, tuple[str, ...]]]:
    records = list(_EXPLICIT_CANDIDATES.get((domain, operation), ()))
    generated = _candidate_names(operation)
    for module_name in _DOMAIN_MODULES.get(domain, (domain,)):
        records.append((module_name, generated))
    deduped = []
    seen = set()
    for module_name, names in records:
        key = (module_name, names)
        if key not in seen:
            seen.add(key)
            deduped.append((module_name, names))
    return deduped


def bridge_adapter_record(domain: str, operation: str) -> dict:
    """Return the forced-live adapter record for a catalog operation."""

    candidates = _candidate_records(domain, operation)
    read_prefixes = ("get_", "list_", "is_", "read_")
    return {
        "operation_id": f"{domain}.{operation}",
        "callable_candidates": [
            {"module": module_name, "functions": list(functions)}
            for module_name, functions in candidates
        ],
        "failure_code": "api_missing",
        "mutation_risk_class": "read"
        if operation == "status" or operation.startswith(read_prefixes)
        else "write",
    }


def _attempt_metadata(candidates: list[tuple[str, tuple[str, ...]]]) -> dict:
    modules = []
    functions = []
    for module_name, names in candidates:
        if module_name not in modules:
            modules.append(module_name)
        for name in names:
            qualified = f"{module_name}.{name}"
            if qualified not in functions:
                functions.append(qualified)
    return {"attempted_modules": modules, "attempted_functions": functions}


def _int_payload(payload: dict, *names: str, default: int) -> int:
    for name in names:
        value = payload.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
    return default


def _float_payload(payload: dict, *names: str, default: float) -> float:
    for name in names:
        value = payload.get(name)
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except ValueError:
                pass
    return default


def _primary_index(payload: dict) -> int:
    return _int_payload(
        payload,
        "index",
        "track_index",
        "channel_index",
        "pattern_index",
        "clip_index",
        "arrangement_index",
        default=0,
    )


def _primary_value(payload: dict):
    for name in (
        "value",
        "volume",
        "pan",
        "color",
        "name",
        "bpm",
        "tempo",
        "position",
        "position_beats",
        "file_path",
        "path",
        "plugin_name",
        "preset_name",
    ):
        if name in payload:
            return payload[name]
    return None


def _path_error(request: dict, payload: dict) -> dict | None:
    domain = str(request.get("domain", ""))
    operation = str(request.get("operation", ""))
    path_keys = ("file_path", "input_path", "path")
    if domain == "render" and operation == "export":
        path_keys = ("output_path",)
    for key in path_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            continue
        if value.startswith("mock://"):
            return _response(
                request,
                success=False,
                error_code="path_unavailable",
                message=f"Live {domain}.{operation} cannot use mock URI path {value!r}.",
                result={
                    "operation_id": f"{domain}.{operation}",
                    "path_field": key,
                    "path": value,
                    "remediation": "Provide a real path accessible to the FL Studio host.",
                },
            )
        expanded = os.path.abspath(os.path.expanduser(value))
        if key == "output_path":
            parent = os.path.dirname(expanded) or os.getcwd()
            if not os.path.isdir(parent):
                return _response(
                    request,
                    success=False,
                    error_code="path_unavailable",
                    message=f"Output directory does not exist: {parent}",
                    result={
                        "operation_id": f"{domain}.{operation}",
                        "path_field": key,
                        "path": expanded,
                        "remediation": (
                            "Create the output directory or choose a writable path "
                            "accessible to FL Studio."
                        ),
                    },
                )
        elif not os.path.exists(expanded):
            return _response(
                request,
                success=False,
                error_code="path_unavailable",
                message=f"Input path does not exist: {expanded}",
                result={
                    "operation_id": f"{domain}.{operation}",
                    "path_field": key,
                    "path": expanded,
                    "remediation": "Provide an existing input path accessible to FL Studio.",
                },
            )
    return None


def _call_variants(payload: dict) -> list[tuple]:
    index = _primary_index(payload)
    value = _primary_value(payload)
    variants = [()]
    if value is not None:
        variants.extend([(value,), (index, value)])
    variants.append((index,))
    if "dest_index" in payload:
        dest_index = _int_payload(payload, "dest_index", "destination_track_index", default=0)
        variants.append((index, dest_index))
        if value is not None:
            variants.append((index, dest_index, value))
    if "param_index" in payload or "parameter_index" in payload:
        param_index = _int_payload(payload, "param_index", "parameter_index", default=0)
        slot_index = _int_payload(payload, "plugin_slot", "slot_index", default=-1)
        variants.append((index, param_index))
        variants.append((param_index, index))
        variants.append((param_index, index, slot_index))
        if value is not None:
            variants.append((index, param_index, value))
            variants.append((value, param_index, index))
            variants.append((value, param_index, index, slot_index))
    variants.append((payload,))
    deduped = []
    for variant in variants:
        if variant not in deduped:
            deduped.append(variant)
    return deduped


def _normalize_live_value(domain: str, operation: str, payload: dict, value) -> dict:
    if isinstance(value, dict):
        result = dict(value)
    elif isinstance(value, (list, tuple)):
        result = {"items": list(value), "count": len(value)}
    elif value is None:
        result = {"applied": True}
    else:
        result = {"value": value}
    result.setdefault("operation_id", f"{domain}.{operation}")
    result.setdefault("payload", payload)
    return result


def _execute_forced_live_adapter(request: dict, payload: dict) -> dict:
    domain = str(request.get("domain", ""))
    operation = str(request.get("operation", ""))
    path_error = _path_error(request, payload)
    if path_error is not None:
        return path_error

    candidates = _candidate_records(domain, operation)
    metadata = _attempt_metadata(candidates)

    if domain == "transport" and operation in {"get_tempo", "get_state"}:
        try:
            tempo = _current_tempo()
            return _response(
                request,
                success=True,
                message="Read transport state through MIDI script host.",
                result={
                    "operation_id": f"{domain}.{operation}",
                    "tempo": tempo,
                    "bpm": tempo,
                    "playing": _is_playing(),
                    **metadata,
                },
            )
        except Exception:
            pass

    if domain == "transport" and operation == "set_tempo":
        try:
            tempo = _float_payload(payload, "bpm", "tempo", default=_current_tempo())
            _set_tempo(tempo)
            return _response(
                request,
                success=True,
                message="Set transport tempo through MIDI script host.",
                result={
                    "operation_id": f"{domain}.{operation}",
                    "tempo": tempo,
                    "bpm": tempo,
                    **metadata,
                },
            )
        except Exception:
            pass

    if domain == "transport" and operation in {"play", "pause", "stop"}:
        try:
            function_names = ("start",) if operation in {"play", "pause"} else ("stop",)
            function = _first_callable(_fl_module("transport"), function_names)
            if function is not None:
                function()
                return _response(
                    request,
                    success=True,
                    message=f"Executed transport.{operation} through MIDI script host.",
                    result={
                        "operation_id": f"{domain}.{operation}",
                        "playing": _is_playing(),
                        **metadata,
                    },
                )
        except Exception:
            pass

    last_type_error = None
    for module_name, function_names in candidates:
        module = _fl_module(module_name)
        if module is None:
            continue
        for function_name in function_names:
            function = getattr(module, function_name, None)
            if not callable(function):
                continue
            for args in _call_variants(payload):
                try:
                    value = function(*args)
                    return _response(
                        request,
                        success=True,
                        message=(
                            f"Executed {domain}.{operation} through FL host "
                            f"{module_name}.{function_name}."
                        ),
                        result={
                            **_normalize_live_value(domain, operation, payload, value),
                            **metadata,
                            "called_module": module_name,
                            "called_function": function_name,
                        },
                    )
                except TypeError as exc:
                    last_type_error = exc
                    continue
                except Exception as exc:
                    return _response(
                        request,
                        success=False,
                        error_code="host_exception",
                        message=f"{type(exc).__name__}: {exc}",
                        result={
                            "operation_id": f"{domain}.{operation}",
                            **metadata,
                            "called_module": module_name,
                            "called_function": function_name,
                            "remediation": "Inspect FL Studio host API support for this operation.",
                        },
                    )

    message = f"FL host API callable not found for {domain}.{operation}."
    if last_type_error is not None:
        message = (
            f"FL host API callable candidates rejected payload for {domain}.{operation}: "
            f"{last_type_error}"
        )
    error_code = "unsupported_host_behavior" if last_type_error is not None else "api_missing"
    remediation = (
        "Adjust the request payload for the callable shape exposed by this FL Studio host, "
        "or register a custom provider."
        if last_type_error is not None
        else (
            "Install/update the bundled FL MCP Bridge, verify the FL MIDI scripting "
            "API exposes this operation, or register a custom provider."
        )
    )
    return _response(
        request,
        success=False,
        error_code=error_code,
        message=message,
        result={
            "operation_id": f"{domain}.{operation}",
            **metadata,
            "remediation": remediation,
        },
    )


def _current_tempo() -> float:
    getter = _first_callable(transport, ("getCurrentTempo", "getTempo", "get_tempo"))
    if getter is not None:
        return float(getter())
    mixer_getter = _first_callable(mixer, ("getCurrentTempo",))
    if mixer_getter is not None:
        try:
            value = float(mixer_getter())
        except TypeError:
            value = float(mixer_getter(0))
        return value / 1000.0 if abs(value) > 400 else value
    raise RuntimeError("No FL Studio tempo getter is available.")


def _set_tempo(value: float) -> None:
    setter = _first_callable(transport, ("setCurrentTempo", "setTempo", "set_tempo"))
    setter_value = value
    if setter is None:
        setter = _first_callable(mixer, ("setCurrentTempo",))
        setter_value = value * 1000.0
    if setter is None:
        raise RuntimeError("No FL Studio tempo setter is available.")
    try:
        setter(setter_value)
    except TypeError:
        setter(setter_value, 0)


def _is_playing() -> bool:
    getter = _first_callable(transport, ("isPlaying",))
    return bool(getter()) if getter is not None else False


def _handle_request(request: dict) -> dict:
    payload = request.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    return _execute_forced_live_adapter(request, payload)


def _write_status(state: str, message: str, extra: dict | None = None) -> None:
    try:
        bridge_dir = _ensure_private_bridge_dir(_bridge_dir())
        payload = {
            "state": state,
            "message": message,
            "bridge_dir": bridge_dir,
            "updated_at": time.time(),
        }
        if extra:
            payload.update(extra)
        _write_json_atomic(
            os.path.join(bridge_dir, STATUS_FILE),
            payload,
        )
        _log(f"status {state}: {message} bridge_dir={bridge_dir}")
    except Exception as exc:
        _log(f"status failed: {type(exc).__name__}: {exc}")


def _unseen_request_paths(request_paths: list[str]) -> list[str]:
    now = time.monotonic()
    stale_paths = [
        path
        for path, processed_at in _processed_request_paths.items()
        if now - processed_at > PROCESSED_REQUEST_TTL_SECONDS
    ]
    for path in stale_paths:
        _processed_request_paths.pop(path, None)
    return [path for path in request_paths if path not in _processed_request_paths]


def _remember_processed_request(request_path: str) -> None:
    _processed_request_paths[request_path] = time.monotonic()
    if len(_processed_request_paths) <= MAX_PROCESSED_REQUESTS:
        return
    oldest_paths = sorted(_processed_request_paths, key=_processed_request_paths.get)
    for path in oldest_paths[: len(_processed_request_paths) - MAX_PROCESSED_REQUESTS]:
        _processed_request_paths.pop(path, None)


def _process_one_request() -> bool:
    global _processed_request_count, _last_bridge_error
    try:
        bridge_dir = _ensure_private_bridge_dir(_bridge_dir())
    except Exception as exc:
        _last_bridge_error = f"{type(exc).__name__}: {exc}"
        _log(f"bridge directory unavailable: {type(exc).__name__}: {exc}")
        return False
    try:
        request_paths = sorted(
            os.path.join(bridge_dir, name)
            for name in os.listdir(bridge_dir)
            if name.startswith("request-") and name.endswith(".json") and not name.endswith(".tmp")
        )
    except OSError as exc:
        _last_bridge_error = f"{type(exc).__name__}: {exc}"
        _log(f"request scan failed: {type(exc).__name__}: {exc}")
        return False
    request_paths = _unseen_request_paths(request_paths)
    if not request_paths:
        return False

    request_path = request_paths[0]
    try:
        with open(request_path, encoding="utf-8") as handle:
            envelope = json.load(handle)
        if not isinstance(envelope, dict):
            raise ValueError("Request envelope must be a JSON object.")
        request_id, request = _request_from_envelope(envelope)
        response = _handle_request(request)
    except Exception as exc:
        request_name = os.path.basename(request_path)
        request_id = request_name.replace("request-", "", 1)
        if request_id.endswith(".json"):
            request_id = request_id[:-5]
        request = {"domain": "controller", "operation": "host_error", "provider": "flapi-live"}
        response = _response(
            request,
            success=False,
            error_code="host_exception",
            message=f"{type(exc).__name__}: {exc}",
            result={"traceback": traceback.format_exc(limit=4)},
        )

    try:
        _write_json_atomic(os.path.join(bridge_dir, f"response-{request_id}.json"), response)
    except Exception as exc:
        _last_bridge_error = f"{type(exc).__name__}: {exc}"
        _log(f"response write failed for {request_id}: {type(exc).__name__}: {exc}")
        return False
    _remember_processed_request(request_path)
    _processed_request_count += 1
    if response.get("success"):
        _last_bridge_error = None
    else:
        _last_bridge_error = f"{response.get('error_code')}: {response.get('message')}"
    _log(f"processed request {request_id}: success={response.get('success')}")
    return True


def _write_poll_status(reason: str, *, processed: bool) -> None:
    _write_status(
        "ready",
        "FL MCP Bridge MIDI script polling.",
        {
            "poll_reason": reason,
            "last_poll_at": time.time(),
            "processed_request_count": _processed_request_count,
            "processed_request": bool(processed),
            "last_error": _last_bridge_error,
        },
    )


def _poll(reason: str, *, force: bool = False) -> None:
    global _last_poll_at, _last_status_at
    now = time.monotonic()
    if not force and now - _last_poll_at < MIN_POLL_INTERVAL_SECONDS:
        return
    _last_poll_at = now
    processed = _process_one_request()

    wall_now = time.time()
    if processed or wall_now - _last_status_at >= STATUS_HEARTBEAT_INTERVAL_SECONDS:
        _last_status_at = wall_now
        _write_poll_status(reason, processed=processed)


def OnInit():  # noqa: N802 - FL Studio requires this callback name.
    global _last_status_at
    _log("OnInit")
    _last_status_at = time.time()
    _write_status(
        "ready",
        "FL MCP Bridge MIDI script initialized.",
        {
            "poll_reason": "init",
            "processed_request_count": _processed_request_count,
            "last_error": _last_bridge_error,
        },
    )


def OnDeInit():  # noqa: N802 - FL Studio requires this callback name.
    _log("OnDeInit")
    _write_status(
        "stopped",
        "FL MCP Bridge MIDI script stopped.",
        {
            "poll_reason": "deinit",
            "processed_request_count": _processed_request_count,
            "last_error": _last_bridge_error,
        },
    )


def OnIdle():  # noqa: N802 - FL Studio requires this callback name.
    _poll("idle")


def OnRefresh(flags=0):  # noqa: N802 - FL Studio requires this callback name.
    _poll("refresh")


def OnUpdateBeatIndicator(value=0):  # noqa: N802 - FL Studio requires this callback name.
    _poll("beat")


def OnDirtyMixerTrack(track=-1):  # noqa: N802 - FL Studio requires this callback name.
    _poll("mixer")


def OnMidiMsg(event=None):  # noqa: N802 - FL Studio requires this callback name.
    _poll("midi")
