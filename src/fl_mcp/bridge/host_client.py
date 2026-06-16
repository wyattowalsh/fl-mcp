"""File-queue client for the FL Studio in-process controller script."""

from __future__ import annotations

import json
import os
import stat
import sys
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse

BRIDGE_DIR_ENV = "FL_MCP_FL_STUDIO_BRIDGE_DIR"
DEFAULT_BRIDGE_DIR = str(Path.home() / ".fl-mcp" / "flstudio-bridge")
POLL_INTERVAL_ENV = "FL_MCP_FL_STUDIO_BRIDGE_POLL_SECONDS"
DEFAULT_POLL_INTERVAL_SECONDS = 0.05
DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS = 15.0
_PRIVATE_DIR_MODE = 0o700


class FileBridgeEnvelope(BaseModel):
    """Request envelope exchanged with the FL Studio MIDI script."""

    request_id: str = Field(min_length=1)
    request: BridgeLiveRequest


def bridge_dir_from_environment() -> Path:
    """Return the request/response directory used by the FL Studio script bridge."""

    return Path(os.getenv(BRIDGE_DIR_ENV, DEFAULT_BRIDGE_DIR)).expanduser()


def ensure_private_bridge_dir(bridge_dir: Path) -> Path:
    """Create or verify a private per-user bridge directory."""

    request_dir = bridge_dir.expanduser()
    if request_dir.exists():
        if request_dir.is_symlink():
            raise ValueError(f"Bridge directory must not be a symlink: {request_dir}.")
        if not request_dir.is_dir():
            raise ValueError(f"Bridge path must be a directory: {request_dir}.")
    else:
        request_dir.mkdir(parents=True, mode=_PRIVATE_DIR_MODE, exist_ok=True)

    if os.name == "posix":
        owner = getattr(os, "getuid", lambda: None)()
        current_stat = request_dir.stat()
        if owner is not None and current_stat.st_uid != owner:
            raise ValueError(f"Bridge directory is not owned by the current user: {request_dir}.")
        if stat.S_IMODE(current_stat.st_mode) != _PRIVATE_DIR_MODE:
            request_dir.chmod(_PRIVATE_DIR_MODE)
            current_stat = request_dir.stat()
        if stat.S_IMODE(current_stat.st_mode) != _PRIVATE_DIR_MODE:
            raise ValueError(f"Bridge directory permissions must be 0700: {request_dir}.")

    return request_dir


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


def _read_response(path: Path) -> BridgeLiveResponse:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    return BridgeLiveResponse.model_validate(decoded)


def run_file_bridge(
    request: BridgeLiveRequest,
    *,
    bridge_dir: Path | None = None,
    timeout_seconds: float = DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS,
    poll_interval_seconds: float | None = None,
    keep_files: bool = False,
) -> BridgeLiveResponse:
    """Submit one bridge request and wait for the FL Studio script response."""

    requested_dir = bridge_dir or bridge_dir_from_environment()
    try:
        request_dir = ensure_private_bridge_dir(requested_dir)
    except ValueError as exc:
        return _response(
            request,
            success=False,
            error_code="bridge_dir_insecure",
            message=str(exc),
            result={"bridge_dir": str(requested_dir.expanduser())},
        )
    request_id = uuid.uuid4().hex
    request_path = request_dir / f"request-{request_id}.json"
    response_path = request_dir / f"response-{request_id}.json"
    envelope = FileBridgeEnvelope(request_id=request_id, request=request)

    _write_json_atomic(
        request_path,
        envelope.model_dump(mode="json"),
    )

    poll_interval = poll_interval_seconds or _poll_interval_from_environment()
    last_response_error: Exception | None = None
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                response = _read_response(response_path)
            except (OSError, json.JSONDecodeError, ValidationError) as exc:
                last_response_error = exc
                time.sleep(poll_interval)
                continue
            if not keep_files:
                request_path.unlink(missing_ok=True)
                response_path.unlink(missing_ok=True)
            return response
        time.sleep(poll_interval)

    if not keep_files:
        request_path.unlink(missing_ok=True)
        if last_response_error is not None:
            response_path.unlink(missing_ok=True)
    if last_response_error is not None:
        return _response(
            request,
            success=False,
            error_code="invalid_response",
            message=(
                "Timed out waiting for a complete FL Studio host script response: "
                f"{type(last_response_error).__name__}: {last_response_error}"
            ),
            execution_id=f"filebridge-{request_id}",
            result={
                "bridge_dir": str(request_dir),
                "request_id": request_id,
                "response_path": str(response_path),
            },
        )
    return _response(
        request,
        success=False,
        error_code="fl_host_timeout",
        message=(
            "Timed out waiting for FL Studio host script response. "
            f"Ensure the FL MCP Bridge MIDI script is enabled and polling {request_dir}."
        ),
        execution_id=f"filebridge-{request_id}",
        result={"bridge_dir": str(request_dir), "request_id": request_id},
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by ``FL_MCP_FL_STUDIO_BRIDGE_CMD``."""

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
        response = run_file_bridge(request)
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
