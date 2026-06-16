"""Repo-owned FL Studio live bridge command.

The command accepts the JSON request contract produced by ``FLStudioBridge`` as
``argv[1]`` and writes exactly one JSON response object to stdout. It supports a
deterministic harness mode for CI and defers FL Studio API imports until a live
operation is dispatched inside an FL Studio Python host.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse

HARNESS_ENV = "FL_MCP_CONTROLLER_HARNESS"
HARNESS_ENV_ALIASES = ("FL_MCP_CONTROLLER_HARNESS", "FL_MCP_LIVE_HARNESS")
HARNESS_STATE_ENV = "FL_MCP_CONTROLLER_HARNESS_STATE"
DEFAULT_HARNESS_STATE = "/tmp/fl-mcp-controller-harness-state.json"


def _response(
    request: BridgeLiveRequest,
    *,
    success: bool,
    result: dict[str, object] | None = None,
    error_code: str | None = None,
    message: str = "",
) -> dict[str, object]:
    response = BridgeLiveResponse(
        success=success,
        result=result or {},
        error_code=error_code,
        message=message,
        execution_id=f"controller-{request.domain}-{request.operation}",
        provider=request.provider or "flapi-live",
    )
    payload = response.model_dump()
    payload["domain"] = request.domain
    payload["operation"] = request.operation
    return payload


def _state_path() -> Path:
    return Path(os.getenv(HARNESS_STATE_ENV, DEFAULT_HARNESS_STATE))


def _read_harness_state() -> dict[str, object]:
    path = _state_path()
    if not path.exists():
        return {"tempo": 120.0, "playing": False, "project_title": "FL MCP Harness"}
    try:
        decoded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"tempo": 120.0, "playing": False, "project_title": "FL MCP Harness"}
    return decoded if isinstance(decoded, dict) else {}


def _write_harness_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def _float_payload(payload: dict[str, object], *names: str, default: float) -> float:
    for name in names:
        value = payload.get(name)
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except ValueError:
                continue
    return default


def _float_state(state: dict[str, object], key: str, default: float) -> float:
    value = state.get(key, default)
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _handle_harness(request: BridgeLiveRequest) -> dict[str, object]:
    state = _read_harness_state()
    if request.domain == "general" and request.operation == "get_version":
        return _response(
            request,
            success=True,
            result={"version": "FL Studio harness", "build": "fl-mcp"},
            message="Harness returned FL Studio version metadata.",
        )
    if request.domain == "general" and request.operation == "get_project_title":
        return _response(
            request,
            success=True,
            result={"title": str(state.get("project_title", "FL MCP Harness"))},
            message="Harness returned project title.",
        )
    if request.domain == "transport" and request.operation in {"get_tempo", "get_state"}:
        tempo = _float_state(state, "tempo", 120.0)
        result: dict[str, object] = {
            "tempo": tempo,
            "bpm": tempo,
            "playing": bool(state.get("playing", False)),
        }
        return _response(request, success=True, result=result, message="Harness read transport.")
    if request.domain == "transport" and request.operation == "set_tempo":
        tempo = _float_payload(request.payload, "bpm", "tempo", default=120.0)
        state["tempo"] = tempo
        _write_harness_state(state)
        return _response(
            request,
            success=True,
            result={"tempo": tempo, "bpm": tempo},
            message="Harness set transport tempo.",
        )
    if request.domain == "transport" and request.operation in {"play", "stop", "pause"}:
        state["playing"] = request.operation == "play"
        _write_harness_state(state)
        return _response(
            request,
            success=True,
            result={"playing": bool(state["playing"])},
            message=f"Harness executed transport.{request.operation}.",
        )
    return _response(
        request,
        success=False,
        error_code="unsupported_operation",
        message=f"Harness bridge does not implement {request.domain}.{request.operation}.",
    )


def _import_fl_module(name: str) -> Any:
    return __import__(name)


def _first_callable(module: Any, names: tuple[str, ...]) -> Callable[..., Any] | None:
    for name in names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return cast(Callable[..., Any], candidate)
    return None


def _call_with_optional_zero_arg(callable_: Callable[..., Any]) -> Any:
    try:
        return callable_()
    except TypeError:
        return callable_(0)


def _call_with_optional_zero_arg_after_value(callable_: Callable[..., Any], value: float) -> Any:
    try:
        return callable_(value)
    except TypeError:
        return callable_(value, 0)


def _normalize_mixer_tempo(value: float) -> float:
    return value / 1000.0 if abs(value) > 400 else value


def _handle_live_fl_api(request: BridgeLiveRequest) -> dict[str, object]:
    try:
        if request.domain == "general" and request.operation == "get_version":
            general = _import_fl_module("general")
            getter = _first_callable(general, ("getVersion", "get_version"))
            version = getter() if getter is not None else "unknown"
            return _response(
                request,
                success=True,
                result={"version": str(version)},
                message="Read FL Studio version through the FL Python API.",
            )
        if request.domain == "transport" and request.operation == "get_tempo":
            transport = _import_fl_module("transport")
            mixer = _import_fl_module("mixer")
            getter = _first_callable(
                transport,
                ("getCurrentTempo", "getTempo", "get_tempo"),
            )
            uses_mixer_tempo = False
            if getter is None:
                getter = _first_callable(mixer, ("getCurrentTempo",))
                uses_mixer_tempo = getter is not None
            if getter is None:
                raise AttributeError("transport.getCurrentTempo or mixer.getCurrentTempo")
            tempo = float(_call_with_optional_zero_arg(getter))
            if uses_mixer_tempo:
                tempo = _normalize_mixer_tempo(tempo)
            return _response(
                request,
                success=True,
                result={"tempo": tempo, "bpm": tempo},
                message="Read FL Studio tempo through the FL Python API.",
            )
        if request.domain == "transport" and request.operation == "set_tempo":
            transport = _import_fl_module("transport")
            mixer = _import_fl_module("mixer")
            setter = _first_callable(
                transport,
                ("setCurrentTempo", "setTempo", "set_tempo"),
            )
            setter_value = tempo = _float_payload(request.payload, "bpm", "tempo", default=120.0)
            if setter is None:
                setter = _first_callable(mixer, ("setCurrentTempo",))
                setter_value = tempo * 1000.0
            if setter is None:
                raise AttributeError("transport.setCurrentTempo or mixer.setCurrentTempo")
            _call_with_optional_zero_arg_after_value(setter, setter_value)
            return _response(
                request,
                success=True,
                result={"tempo": tempo, "bpm": tempo},
                message="Set FL Studio tempo through the FL Python API.",
            )
    except ModuleNotFoundError as exc:
        return _response(
            request,
            success=False,
            error_code="fl_api_unavailable",
            message=f"FL Studio API module unavailable: {exc.name}.",
        )
    except Exception as exc:  # pragma: no cover - host API behaviour is external.
        return _response(
            request,
            success=False,
            error_code="fl_api_error",
            message=f"FL Studio API error: {type(exc).__name__}: {exc}",
        )

    return _response(
        request,
        success=False,
        error_code="unsupported_operation",
        message=f"Live controller bridge does not implement {request.domain}.{request.operation}.",
    )


def handle_request(request: BridgeLiveRequest, *, force_harness: bool = False) -> dict[str, object]:
    """Dispatch one validated bridge request."""
    if request.domain not in DOMAINS:
        return _response(
            request,
            success=False,
            error_code="unsupported_domain",
            message=f"Domain is not registered: {request.domain}.",
        )
    harness_from_env = any(
        os.getenv(name, "").strip().lower() in {"1", "true", "yes"} for name in HARNESS_ENV_ALIASES
    )
    if force_harness or harness_from_env:
        return _handle_harness(request)
    return _handle_live_fl_api(request)


def _parse_args(args: list[str]) -> tuple[str, list[str]]:
    mode = "auto"
    remaining = list(args)
    if remaining and remaining[0] == "--harness":
        mode = "harness"
        remaining = remaining[1:]
    if len(remaining) >= 2 and remaining[0] == "--mode":
        mode = remaining[1]
        remaining = remaining[2:]
    return mode, remaining


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by ``FL_MCP_FL_STUDIO_BRIDGE_CMD``."""
    mode, args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if len(args) != 1:
        request = BridgeLiveRequest(domain="controller", operation="parse", provider="flapi-live")
        print(
            json.dumps(
                _response(
                    request,
                    success=False,
                    error_code="invalid_request",
                    message="Expected exactly one JSON request argument.",
                ),
                sort_keys=True,
            )
        )
        return 2
    try:
        request = BridgeLiveRequest.model_validate_json(args[0])
        response = handle_request(request, force_harness=mode == "harness")
    except (json.JSONDecodeError, ValueError) as exc:
        request = BridgeLiveRequest(domain="controller", operation="parse", provider="flapi-live")
        response = _response(
            request,
            success=False,
            error_code="invalid_request",
            message=str(exc),
        )
    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
