"""Tests for optional bridge idempotency keys."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from fl_mcp.bridge.host_client import (
    DEFAULT_IDEMPOTENCY_TTL_SECONDS,
    FileBridgeEnvelope,
    _request_fingerprint,
    _request_id_for_bridge,
    _sanitize_idempotency_key,
    _write_completed_cache,
    run_file_bridge,
)
from fl_mcp.bridge.selected_controller_client import (
    _lock_is_stale,
    run_selected_controller_bridge,
)
from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse


def test_sanitize_idempotency_key_normalizes_unsafe_characters() -> None:
    assert _sanitize_idempotency_key(" tempo/set#1 ") == "tempo-set-1"


def test_request_id_for_bridge_uses_idempotency_key() -> None:
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="retry-tempo-1",
    )

    request_id, idempotency_key = _request_id_for_bridge(request)

    assert request_id == "retry-tempo-1"
    assert idempotency_key == "retry-tempo-1"


def test_run_file_bridge_rejects_invalid_idempotency_key(tmp_path: Path) -> None:
    response = run_file_bridge(
        BridgeLiveRequest(
            domain="transport",
            operation="get_tempo",
            provider="flapi-live",
            idempotency_key="###",
        ),
        bridge_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
    )

    assert response.success is False
    assert response.error_code == "invalid_idempotency_key"
    assert not list(tmp_path.glob("request-*.json"))


def test_run_file_bridge_returns_cached_response_for_idempotency_key(tmp_path: Path) -> None:
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="retry-tempo-1",
    )
    cached = BridgeLiveResponse(
        success=True,
        message="cached response",
        execution_id="cached-1",
        provider="flapi-live",
        result={"tempo": 140.0},
    )
    envelope = FileBridgeEnvelope(
        request_id="retry-tempo-1",
        request=request,
        idempotency_key="retry-tempo-1",
    )
    (tmp_path / "request-retry-tempo-1.json").write_text(
        json.dumps(envelope.model_dump(mode="json", exclude_none=True)),
        encoding="utf-8",
    )
    (tmp_path / "response-retry-tempo-1.json").write_text(
        json.dumps(cached.model_dump(mode="json")),
        encoding="utf-8",
    )

    response = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
    )

    assert response.success is True
    assert response.message == "cached response"
    assert response.result["tempo"] == 140.0
    assert not list(tmp_path.glob("request-*.json"))


def test_run_file_bridge_reports_idempotency_mismatch_for_same_key(tmp_path: Path) -> None:
    cached_request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="retry-tempo-1",
    )
    cached = BridgeLiveResponse(
        success=True,
        message="cached response",
        execution_id="cached-1",
        provider="flapi-live",
        result={"tempo": 140.0},
    )
    envelope = FileBridgeEnvelope(
        request_id="retry-tempo-1",
        request=cached_request,
        idempotency_key="retry-tempo-1",
    )
    (tmp_path / "request-retry-tempo-1.json").write_text(
        json.dumps(envelope.model_dump(mode="json", exclude_none=True)),
        encoding="utf-8",
    )
    (tmp_path / "response-retry-tempo-1.json").write_text(
        json.dumps(cached.model_dump(mode="json")),
        encoding="utf-8",
    )

    response = run_file_bridge(
        BridgeLiveRequest(
            domain="transport",
            operation="set_tempo",
            provider="flapi-live",
            payload={"bpm": 140},
            idempotency_key="retry-tempo-1",
        ),
        bridge_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
    )

    assert response.success is False
    assert response.error_code == "idempotency_mismatch"


def test_run_file_bridge_reuses_completed_cache_after_cleanup(tmp_path: Path) -> None:
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="retry-tempo-1",
    )
    cached = BridgeLiveResponse(
        success=True,
        message="completed cache",
        execution_id="cached-1",
        provider="flapi-live",
        result={"tempo": 141.0},
    )
    _write_completed_cache(
        tmp_path / "completed-retry-tempo-1.json",
        fingerprint=_request_fingerprint(request),
        response=cached,
    )

    response = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
    )

    assert response.success is True
    assert response.message == "completed cache"
    assert response.result["tempo"] == 141.0
    assert not list(tmp_path.glob("request-*.json"))


def test_run_file_bridge_ignores_expired_completed_cache(tmp_path: Path) -> None:
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="retry-tempo-1",
    )
    cached = BridgeLiveResponse(
        success=True,
        message="stale cache",
        execution_id="cached-1",
        provider="flapi-live",
        result={"tempo": 141.0},
    )
    completed_path = tmp_path / "completed-retry-tempo-1.json"
    _write_completed_cache(
        completed_path,
        fingerprint=_request_fingerprint(request),
        response=cached,
    )
    completed_path.write_text(
        json.dumps(
            {
                "fingerprint": _request_fingerprint(request),
                "response": cached.model_dump(mode="json"),
                "completed_at": time.time() - DEFAULT_IDEMPOTENCY_TTL_SECONDS - 5,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    response = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=0.05,
        poll_interval_seconds=0.01,
    )

    assert response.success is False
    assert response.error_code == "fl_host_timeout"
    assert not list(tmp_path.glob("request-retry-tempo-1.json"))


def test_run_file_bridge_reuses_request_id_for_duplicate_submission(tmp_path: Path) -> None:
    host_calls: list[str] = []

    def host_worker() -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            matches = sorted(tmp_path.glob("request-*.json"))
            if matches:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("request file was not created")

        request_path = matches[0]
        envelope = FileBridgeEnvelope.model_validate_json(request_path.read_text())
        host_calls.append(envelope.request_id)
        response = BridgeLiveResponse(
            success=True,
            message="host ok",
            execution_id="host-idem",
            provider="flapi-live",
            result={"request_id": envelope.request_id},
        )
        response_path = tmp_path / f"response-{envelope.request_id}.json"
        response_path.write_text(json.dumps(response.model_dump(mode="json")), encoding="utf-8")

    worker = threading.Thread(target=host_worker)
    worker.start()

    request = BridgeLiveRequest(
        domain="transport",
        operation="set_tempo",
        provider="flapi-live",
        payload={"bpm": 132},
        idempotency_key="stable-set-tempo",
    )
    first = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
        keep_files=True,
    )
    worker.join(timeout=2)

    assert first.success is True
    assert host_calls == ["stable-set-tempo"]
    assert (tmp_path / "request-stable-set-tempo.json").exists()
    assert (tmp_path / "response-stable-set-tempo.json").exists()

    second = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
        keep_files=True,
    )

    assert second.success is True
    assert second.message == "host ok"
    assert host_calls == ["stable-set-tempo"]


def test_run_file_bridge_writes_completed_cache_on_success(tmp_path: Path) -> None:
    def host_worker() -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            matches = sorted(tmp_path.glob("request-*.json"))
            if matches:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("request file was not created")

        request_path = matches[0]
        envelope = FileBridgeEnvelope.model_validate_json(request_path.read_text())
        response = BridgeLiveResponse(
            success=True,
            message="host ok",
            execution_id="host-idem",
            provider="flapi-live",
            result={"request_id": envelope.request_id, "tempo": 132.0},
        )
        response_path = tmp_path / f"response-{envelope.request_id}.json"
        response_path.write_text(json.dumps(response.model_dump(mode="json")), encoding="utf-8")

    worker = threading.Thread(target=host_worker)
    worker.start()

    request = BridgeLiveRequest(
        domain="transport",
        operation="set_tempo",
        provider="flapi-live",
        payload={"bpm": 132},
        idempotency_key="stable-set-tempo",
    )
    response = run_file_bridge(
        request,
        bridge_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert (tmp_path / "completed-stable-set-tempo.json").exists()
    assert not list(tmp_path.glob("request-*.json"))
    assert not list(tmp_path.glob("response-*.json"))


def test_selected_controller_bridge_returns_completed_cache(tmp_path: Path) -> None:
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="selected-tempo-1",
    )
    cached = BridgeLiveResponse(
        success=True,
        message="selected cache",
        execution_id="selected-1",
        provider="flapi-live",
        result={"tempo": 128.0},
    )
    _write_completed_cache(
        tmp_path / "completed-selected-tempo-1.json",
        fingerprint=_request_fingerprint(request),
        response=cached,
    )

    response = run_selected_controller_bridge(
        request,
        controller_dir=tmp_path,
        timeout_seconds=0.2,
        poll_interval_seconds=0.01,
    )

    assert response.success is True
    assert response.message == "selected cache"
    assert response.result["tempo"] == 128.0
    assert not (tmp_path / "mcp_command.json").exists()


def test_selected_controller_bridge_writes_completed_cache_on_success(tmp_path: Path) -> None:
    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, "tempo": 130.0}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    request = BridgeLiveRequest(
        domain="transport",
        operation="get_tempo",
        provider="flapi-live",
        idempotency_key="selected-tempo-2",
    )
    response = run_selected_controller_bridge(
        request,
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert (tmp_path / "completed-selected-tempo-2.json").exists()


def test_selected_controller_lock_breaks_stale_dead_pid_lock(tmp_path: Path) -> None:
    stale_pid = 999_999_999
    lock_path = tmp_path / ".mcp_command.lock"
    lock_path.write_text(f"pid={stale_pid} created_at={time.time()}\n", encoding="utf-8")

    assert _lock_is_stale(lock_path) is True

    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, "tempo": 120.0}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(domain="transport", operation="get_tempo", provider="flapi-live"),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert not lock_path.exists()


def test_selected_controller_lock_breaks_stale_age_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / ".mcp_command.lock"
    created_at = 1000.0
    lock_path.write_text(f"pid={os.getpid()} created_at={created_at}\n", encoding="utf-8")
    monkeypatch.setattr("fl_mcp.bridge.selected_controller_client.time.time", lambda: created_at + 120.0)

    assert _lock_is_stale(lock_path) is True