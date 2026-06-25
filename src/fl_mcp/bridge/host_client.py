"""File-queue client for the FL Studio in-process controller script."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
STATUS_FILE_NAME = "status.json"


_IDEMPOTENCY_KEY_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
IDEMPOTENCY_TTL_ENV = "FL_MCP_BRIDGE_IDEMPOTENCY_TTL_SECONDS"
DEFAULT_IDEMPOTENCY_TTL_SECONDS = 3600.0


class FileBridgeEnvelope(BaseModel):
    """Request envelope exchanged with the FL Studio MIDI script."""

    request_id: str = Field(min_length=1)
    request: BridgeLiveRequest
    idempotency_key: str | None = None


def _sanitize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _IDEMPOTENCY_KEY_PATTERN.sub("-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned or None


def _request_fingerprint(request: BridgeLiveRequest) -> str:
    canonical = json.dumps(
        {
            "domain": request.domain,
            "operation": request.operation,
            "payload": request.payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _idempotency_ttl_seconds() -> float:
    raw = os.getenv(IDEMPOTENCY_TTL_ENV)
    if raw is None:
        return DEFAULT_IDEMPOTENCY_TTL_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_IDEMPOTENCY_TTL_SECONDS
    return value if value > 0 else DEFAULT_IDEMPOTENCY_TTL_SECONDS


def _completed_cache_path(bridge_dir: Path, request_id: str) -> Path:
    return bridge_dir / f"completed-{request_id}.json"


def _read_completed_cache_entry(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    return {str(key): value for key, value in decoded.items()}


def _completed_cache_is_fresh(entry: dict[str, object]) -> bool:
    completed_at = entry.get("completed_at")
    if not isinstance(completed_at, int | float):
        return False
    return (time.time() - float(completed_at)) <= _idempotency_ttl_seconds()


def _write_completed_cache(
    path: Path,
    *,
    fingerprint: str,
    response: BridgeLiveResponse,
) -> None:
    _write_json_atomic(
        path,
        {
            "fingerprint": fingerprint,
            "response": response.model_dump(mode="json"),
            "completed_at": time.time(),
        },
    )


def _idempotency_mismatch_response(
    request: BridgeLiveRequest,
    *,
    request_id: str,
    bridge_dir: Path,
) -> BridgeLiveResponse:
    return _response(
        request,
        success=False,
        error_code="idempotency_mismatch",
        message=(
            "Idempotency key was reused with a different request envelope "
            "(domain, operation, or payload)."
        ),
        execution_id=f"filebridge-{request_id}",
        result={
            "bridge_dir": str(bridge_dir),
            "request_id": request_id,
        },
    )


def _invalid_idempotency_key_response(request: BridgeLiveRequest) -> BridgeLiveResponse:
    return _response(
        request,
        success=False,
        error_code="invalid_idempotency_key",
        message="Idempotency key must contain at least one safe character after normalization.",
    )


def _stored_request_fingerprint(
    bridge_dir: Path,
    request_id: str,
    *,
    request_path: Path,
) -> str | None:
    if request_path.exists():
        try:
            envelope = FileBridgeEnvelope.model_validate_json(request_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValidationError):
            return None
        return _request_fingerprint(envelope.request)

    completed_entry = _read_completed_cache_entry(_completed_cache_path(bridge_dir, request_id))
    if completed_entry is None:
        return None
    fingerprint = completed_entry.get("fingerprint")
    return fingerprint if isinstance(fingerprint, str) else None


def _lookup_completed_cache_response(
    request: BridgeLiveRequest,
    *,
    bridge_dir: Path,
    request_id: str,
    fingerprint: str,
) -> BridgeLiveResponse | None:
    entry = _read_completed_cache_entry(_completed_cache_path(bridge_dir, request_id))
    if entry is None or not _completed_cache_is_fresh(entry):
        return None

    stored_fingerprint = entry.get("fingerprint")
    if not isinstance(stored_fingerprint, str):
        return None
    if stored_fingerprint != fingerprint:
        return _idempotency_mismatch_response(
            request,
            request_id=request_id,
            bridge_dir=bridge_dir,
        )

    response_payload = entry.get("response")
    if not isinstance(response_payload, dict):
        return None
    try:
        return BridgeLiveResponse.model_validate(response_payload)
    except ValidationError:
        return None


def _verify_cached_live_response(
    request: BridgeLiveRequest,
    *,
    bridge_dir: Path,
    request_id: str,
    fingerprint: str,
    response_path: Path,
    request_path: Path,
) -> BridgeLiveResponse:
    stored_fingerprint = _stored_request_fingerprint(
        bridge_dir,
        request_id,
        request_path=request_path,
    )
    if stored_fingerprint is None or stored_fingerprint != fingerprint:
        return _idempotency_mismatch_response(
            request,
            request_id=request_id,
            bridge_dir=bridge_dir,
        )
    return _read_response(response_path)


def _request_id_for_bridge(request: BridgeLiveRequest) -> tuple[str, str | None]:
    idempotency_key = _sanitize_idempotency_key(request.idempotency_key)
    if idempotency_key:
        return idempotency_key, idempotency_key
    return uuid.uuid4().hex, None


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


def _try_write_json_exclusive(path: Path, payload: dict[str, object]) -> bool:
    """Create ``path`` with ``O_EXCL`` so concurrent submitters do not overwrite."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return False
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
    return True


def _read_response(path: Path) -> BridgeLiveResponse:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    return BridgeLiveResponse.model_validate(decoded)


def _bridge_status_snapshot(request_dir: Path) -> dict[str, object] | None:
    status_path = request_dir / STATUS_FILE_NAME
    if not status_path.exists():
        return None
    try:
        decoded = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(status_path),
            "read_error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(decoded, dict):
        return {
            "path": str(status_path),
            "read_error": "status.json did not contain a JSON object",
        }
    snapshot = {str(key): value for key, value in decoded.items()}
    snapshot["path"] = str(status_path)
    updated_at = snapshot.get("updated_at")
    if isinstance(updated_at, int | float):
        snapshot["age_seconds"] = max(0.0, time.time() - float(updated_at))
    return snapshot


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
    if request.idempotency_key is not None and _sanitize_idempotency_key(request.idempotency_key) is None:
        return _invalid_idempotency_key_response(request)

    request_id, idempotency_key = _request_id_for_bridge(request)
    request_path = request_dir / f"request-{request_id}.json"
    response_path = request_dir / f"response-{request_id}.json"
    fingerprint = _request_fingerprint(request)
    envelope = FileBridgeEnvelope(
        request_id=request_id,
        request=request,
        idempotency_key=idempotency_key,
    )

    if idempotency_key:
        completed_hit = _lookup_completed_cache_response(
            request,
            bridge_dir=request_dir,
            request_id=request_id,
            fingerprint=fingerprint,
        )
        if completed_hit is not None:
            return completed_hit

    if response_path.exists():
        try:
            cached = _verify_cached_live_response(
                request,
                bridge_dir=request_dir,
                request_id=request_id,
                fingerprint=fingerprint,
                response_path=response_path,
                request_path=request_path,
            )
            if cached.success and not keep_files:
                if idempotency_key:
                    _write_completed_cache(
                        _completed_cache_path(request_dir, request_id),
                        fingerprint=fingerprint,
                        response=cached,
                    )
                request_path.unlink(missing_ok=True)
                response_path.unlink(missing_ok=True)
            return cached
        except (OSError, json.JSONDecodeError, ValidationError):
            pass

    _try_write_json_exclusive(
        request_path,
        envelope.model_dump(mode="json", exclude_none=True),
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
                if idempotency_key:
                    _write_completed_cache(
                        _completed_cache_path(request_dir, request_id),
                        fingerprint=fingerprint,
                        response=response,
                    )
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
                "status": _bridge_status_snapshot(request_dir),
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
        result={
            "bridge_dir": str(request_dir),
            "request_id": request_id,
            "status": _bridge_status_snapshot(request_dir),
            "remediation": (
                "Select the FL MCP Bridge controller in FL Studio MIDI Settings "
                "and confirm status.json updated_at refreshes while FL is open."
            ),
        },
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
