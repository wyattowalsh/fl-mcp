"""Tests for the FL Studio host file bridge."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from fl_mcp.bridge import controller_bridge, host_client
from fl_mcp.bridge.bundle import _active_user_data_dir, bridge_runner_descriptor
from fl_mcp.bridge.host_client import (
    DEFAULT_BRIDGE_DIR,
    FileBridgeEnvelope,
    bridge_dir_from_environment,
    ensure_private_bridge_dir,
    run_file_bridge,
)
from fl_mcp.bridge.selected_controller_client import (
    run_selected_controller_bridge,
)
from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS


def _wait_for_request_file(bridge_dir: Path) -> Path:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        matches = sorted(bridge_dir.glob("request-*.json"))
        if matches:
            return matches[0]
        time.sleep(0.01)
    raise AssertionError("request file was not created")


def _wait_for_command_write(
    command_path: Path,
    previous_mtime: int,
    previous_command: dict[str, object] | None = None,
) -> tuple[dict[str, object], int]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if command_path.exists():
            mtime = command_path.stat().st_mtime_ns
            if mtime > previous_mtime:
                command = json.loads(command_path.read_text(encoding="utf-8"))
                if command != previous_command:
                    return command, mtime
        time.sleep(0.01)
    raise AssertionError("command file was not updated")


def test_bridge_runner_descriptor_resolves_controller_script_from_non_repo_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    descriptor = bridge_runner_descriptor()
    controller_script = Path(descriptor.controller_script)

    assert descriptor.status == "available"
    assert controller_script.exists()
    assert controller_script.name == "device_FL_MCP_Bridge.py"
    assert not controller_script.is_relative_to(tmp_path)


def test_default_file_bridge_dir_is_private_user_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", raising=False)

    default_dir = bridge_dir_from_environment()
    secure_dir = ensure_private_bridge_dir(tmp_path / "bridge")

    assert str(default_dir) == DEFAULT_BRIDGE_DIR
    assert default_dir.name == "flstudio-bridge"
    assert default_dir.parent.name == ".fl-mcp"
    assert secure_dir.is_dir()
    if os.name == "posix":
        assert stat.S_IMODE(secure_dir.stat().st_mode) == 0o700


def test_file_bridge_client_round_trips_through_response_file(tmp_path: Path) -> None:
    def host_worker() -> None:
        request_path = _wait_for_request_file(tmp_path)
        envelope = FileBridgeEnvelope.model_validate_json(request_path.read_text())
        response = BridgeLiveResponse(
            success=True,
            message="host ok",
            execution_id="host-test",
            provider="flapi-live",
            result={"request_id": envelope.request_id, "tempo": 132.0},
        )
        response_path = tmp_path / f"response-{envelope.request_id}.json"
        response_path.write_text(json.dumps(response.model_dump(mode="json")), encoding="utf-8")

    worker = threading.Thread(target=host_worker)
    worker.start()

    response = run_file_bridge(
        BridgeLiveRequest(
            domain="transport",
            operation="set_tempo",
            provider="flapi-live",
            payload={"bpm": 132},
        ),
        bridge_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert response.result["tempo"] == 132.0
    assert not list(tmp_path.glob("request-*.json"))
    assert not list(tmp_path.glob("response-*.json"))


def test_file_bridge_client_waits_for_complete_response_file(tmp_path: Path) -> None:
    def host_worker() -> None:
        request_path = _wait_for_request_file(tmp_path)
        envelope = FileBridgeEnvelope.model_validate_json(request_path.read_text())
        response_path = tmp_path / f"response-{envelope.request_id}.json"
        response_path.write_text("", encoding="utf-8")
        time.sleep(0.05)
        response = BridgeLiveResponse(
            success=True,
            message="host ok after partial write",
            execution_id="host-partial-test",
            provider="flapi-live",
            result={"request_id": envelope.request_id, "tempo": 133.0},
        )
        response_path.write_text(json.dumps(response.model_dump(mode="json")), encoding="utf-8")

    worker = threading.Thread(target=host_worker)
    worker.start()

    response = run_file_bridge(
        BridgeLiveRequest(
            domain="transport",
            operation="get_tempo",
            provider="flapi-live",
            payload={},
        ),
        bridge_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert response.result["tempo"] == 133.0
    assert not list(tmp_path.glob("request-*.json"))
    assert not list(tmp_path.glob("response-*.json"))


def test_file_bridge_client_times_out_when_fl_script_is_not_polling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_now = 1060.5
    stale_updated_at = 1000.0
    monkeypatch.setattr(host_client.time, "time", lambda: snapshot_now)
    stale_status = {
        "state": "ready",
        "message": "old init",
        "updated_at": stale_updated_at,
        "poll_reason": "init",
        "processed_request_count": 0,
    }
    (tmp_path / "status.json").write_text(json.dumps(stale_status), encoding="utf-8")

    response = run_file_bridge(
        BridgeLiveRequest(domain="transport", operation="get_state", provider="flapi-live"),
        bridge_dir=tmp_path,
        timeout_seconds=0.01,
        poll_interval_seconds=0.001,
    )

    assert response.success is False
    assert response.error_code == "fl_host_timeout"
    assert response.result["bridge_dir"] == str(tmp_path)
    status = cast(dict[str, object], response.result["status"])
    assert status["state"] == "ready"
    assert status["poll_reason"] == "init"
    assert status["age_seconds"] == pytest.approx(snapshot_now - stale_updated_at)
    assert "Select the FL MCP Bridge controller" in str(response.result["remediation"])
    assert not list(tmp_path.glob("request-*.json"))


def _write_startup_log(user_data_dir: Path, *, mtime: float) -> None:
    startup_log = user_data_dir / "Support/Logs/Startup/Startup test.log"
    startup_log.parent.mkdir(parents=True, exist_ok=True)
    startup_log.write_text("startup", encoding="utf-8")
    os.utime(startup_log, (mtime, mtime))


def test_active_user_data_dir_prefers_newest_startup_log(tmp_path: Path) -> None:
    image_line = tmp_path / "Documents/Image-Line/FL Studio"
    image_line_2 = tmp_path / "Documents/Image-Line 2/FL Studio"
    _write_startup_log(image_line, mtime=200.0)
    _write_startup_log(image_line_2, mtime=100.0)

    assert _active_user_data_dir(tmp_path) == image_line


def test_active_user_data_dir_falls_back_to_existing_hardware_path(tmp_path: Path) -> None:
    image_line_2 = tmp_path / "Documents/Image-Line 2/FL Studio"
    (image_line_2 / "Settings/Hardware").mkdir(parents=True)

    assert _active_user_data_dir(tmp_path) == image_line_2


def test_selected_controller_client_round_trips_through_existing_script_files(
    tmp_path: Path,
) -> None:
    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        command = json.loads(command_path.read_text(encoding="utf-8"))
        assert command == {
            "action": "mixer.setTrackPan",
            "params": {"pan": 0.25, "track": 7},
        }
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, "pan": 0.25}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(
            domain="mixer",
            operation="set_pan",
            provider="flapi-live",
            payload={"track": 7, "pan": 0.25},
        ),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert response.result["pan"] == 0.25


@pytest.mark.parametrize(
    ("operation", "payload", "expected_command"),
    [
        (
            "get_track_pan",
            {"index": 7},
            {"action": "mixer.getTrackInfo", "params": {"track": 7}},
        ),
        (
            "set_track_pan",
            {"index": 7, "pan": 0.25},
            {"action": "mixer.setTrackPan", "params": {"track": 7, "pan": 0.25}},
        ),
        (
            "set_track_volume",
            {"index": 7, "volume": 0.7},
            {"action": "mixer.setTrackVolume", "params": {"track": 7, "volume": 0.7}},
        ),
    ],
)
def test_selected_controller_client_maps_canonical_mixer_operations(
    tmp_path: Path,
    operation: str,
    payload: dict[str, object],
    expected_command: dict[str, object],
) -> None:
    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        command = json.loads(command_path.read_text(encoding="utf-8"))
        assert command == expected_command
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, **payload}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(
            domain="mixer",
            operation=operation,
            provider="flapi-live",
            payload=payload,
        ),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True


@pytest.mark.parametrize(
    ("operation", "payload", "expected_command"),
    [
        (
            "get_tempo",
            {},
            {"action": "transport.getStatus", "params": {}},
        ),
        (
            "set_tempo",
            {"bpm": 132.0},
            {"action": "transport.setTempo", "params": {"tempo": 132.0}},
        ),
    ],
)
def test_selected_controller_client_maps_canonical_transport_tempo(
    tmp_path: Path,
    operation: str,
    payload: dict[str, object],
    expected_command: dict[str, object],
) -> None:
    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        command = json.loads(command_path.read_text(encoding="utf-8"))
        assert command == expected_command
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, "tempo": 132.0, "bpm": 132.0}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(
            domain="transport",
            operation=operation,
            provider="flapi-live",
            payload=payload,
        ),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert response.result["tempo"] == 132.0


def test_selected_controller_client_serializes_concurrent_requests(tmp_path: Path) -> None:
    command_path = tmp_path / "mcp_command.json"
    responses: list[BridgeLiveResponse] = []

    def host_worker() -> None:
        previous_mtime = 0
        for _ in range(2):
            command, previous_mtime = _wait_for_command_write(command_path, previous_mtime)
            params = cast(dict[str, object], command["params"])
            pan = params["pan"]
            time.sleep(0.03)
            (tmp_path / "mcp_response.json").write_text(
                json.dumps({"success": True, "pan": pan}),
                encoding="utf-8",
            )

    def client_worker(pan: float) -> None:
        response = run_selected_controller_bridge(
            BridgeLiveRequest(
                domain="mixer",
                operation="set_pan",
                provider="flapi-live",
                payload={"track": 7, "pan": pan},
            ),
            controller_dir=tmp_path,
            timeout_seconds=2,
            poll_interval_seconds=0.01,
        )
        responses.append(response)

    host = threading.Thread(target=host_worker)
    clients = [threading.Thread(target=client_worker, args=(pan,)) for pan in (0.15, -0.15)]
    host.start()
    for client in clients:
        client.start()
    for client in clients:
        client.join(timeout=2)
    host.join(timeout=2)

    assert len(responses) == 2
    assert {response.result["pan"] for response in responses} == {0.15, -0.15}
    assert all(response.success for response in responses)
    assert not (tmp_path / ".mcp_command.lock").exists()


def test_selected_controller_client_reports_unsupported_operation(tmp_path: Path) -> None:
    response = run_selected_controller_bridge(
        BridgeLiveRequest(domain="patterns", operation="create_pattern", provider="flapi-live"),
        controller_dir=tmp_path,
    )

    assert response.success is False
    assert response.error_code == "unsupported_operation"


@pytest.mark.parametrize(
    ("domain", "operation", "payload", "expected_command"),
    [
        (
            "transport",
            "set_loop_mode",
            {"mode": "song"},
            {"action": "transport.setLoopMode", "params": {"mode": "song"}},
        ),
        (
            "channels",
            "set_step_sequence",
            {"index": 2, "steps": [0, 4, 8, 12]},
            {
                "action": "channels.setStepSequence",
                "params": {
                    "channel": 2,
                    "pattern": [
                        True,
                        False,
                        False,
                        False,
                        True,
                        False,
                        False,
                        False,
                        True,
                        False,
                        False,
                        False,
                        True,
                        False,
                        False,
                        False,
                    ],
                },
            },
        ),
        (
            "channels",
            "route_to_mixer",
            {"channel_index": 2, "mixer_track_index": 5},
            {
                "action": "channels.routeToMixer",
                "params": {"channel_index": 2, "mixer_track": 5},
            },
        ),
        (
            "plugins",
            "set_parameter",
            {"channel_index": 3, "plugin_slot": 1, "parameter_index": 4, "value": 0.42},
            {
                "action": "plugins.setParamValue",
                "params": {
                    "plugin_index": 3,
                    "slot_index": 1,
                    "param_index": 4,
                    "value": 0.42,
                },
            },
        ),
    ],
)
def test_selected_controller_client_maps_expanded_controller_operations(
    tmp_path: Path,
    domain: str,
    operation: str,
    payload: dict[str, object],
    expected_command: dict[str, object],
) -> None:
    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not command_path.exists():
            time.sleep(0.01)
        command = json.loads(command_path.read_text(encoding="utf-8"))
        assert command == expected_command
        (tmp_path / "mcp_response.json").write_text(
            json.dumps({"success": True, "action": expected_command["action"]}),
            encoding="utf-8",
        )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(
            domain=domain,
            operation=operation,
            provider="flapi-live",
            payload=payload,
        ),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True


def test_selected_controller_client_sequences_update_track_commands(tmp_path: Path) -> None:
    expected_commands = [
        {"action": "mixer.setTrackName", "params": {"track": 4, "name": "HS Kick"}},
        {"action": "mixer.setTrackColor", "params": {"track": 4, "r": 240, "g": 96, "b": 48}},
        {"action": "mixer.setTrackVolume", "params": {"track": 4, "volume": 0.74}},
        {"action": "mixer.setTrackPan", "params": {"track": 4, "pan": -0.1}},
    ]

    def host_worker() -> None:
        command_path = tmp_path / "mcp_command.json"
        previous_mtime = 0
        previous_command: dict[str, object] | None = None
        for index, expected_command in enumerate(expected_commands):
            command, previous_mtime = _wait_for_command_write(
                command_path,
                previous_mtime,
                previous_command,
            )
            assert command == expected_command
            previous_command = command
            (tmp_path / "mcp_response.json").write_text(
                json.dumps({"success": True, "step": index, "action": expected_command["action"]}),
                encoding="utf-8",
            )

    worker = threading.Thread(target=host_worker)
    worker.start()
    response = run_selected_controller_bridge(
        BridgeLiveRequest(
            domain="mixer",
            operation="update_track",
            provider="flapi-live",
            payload={
                "index": 4,
                "name": "HS Kick",
                "color": 0xF06030,
                "volume": 0.74,
                "pan": -0.1,
            },
        ),
        controller_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    worker.join(timeout=2)

    assert response.success is True
    assert response.result["action"] == "mixer.setTrackPan"
    assert len(cast(list[dict[str, object]], response.result["commands"])) == 4


def _load_controller_script() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "fl-bundle" / "controller" / "device_FL_MCP_Bridge.py"
    spec = importlib.util.spec_from_file_location("device_FL_MCP_Bridge_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    cast(Any, spec.loader).exec_module(module)
    return module


def test_fl_controller_script_json_write_avoids_low_level_os_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()

    def fail_os_open(*_args: object, **_kwargs: object) -> int:
        raise TypeError("bad argument type for built-in operation")

    monkeypatch.setattr(module.os, "open", fail_os_open)
    output_path = tmp_path / "status.json"

    module._write_json_atomic(str(output_path), {"state": "ready"})

    assert json.loads(output_path.read_text(encoding="utf-8")) == {"state": "ready"}
    assert not (tmp_path / "status.json.tmp").exists()


def test_fl_controller_script_json_write_tolerates_host_chmod_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()

    def fail_host_file_call(*_args: object, **_kwargs: object) -> None:
        raise TypeError("bad argument type for built-in operation")

    monkeypatch.setattr(module.os, "chmod", fail_host_file_call)
    output_path = tmp_path / "response-live.json"

    module._write_json_atomic(str(output_path), {"success": True})

    assert json.loads(output_path.read_text(encoding="utf-8")) == {"success": True}
    assert not (tmp_path / "response-live.json.tmp").exists()


def test_fl_controller_script_logging_is_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.setattr(module, "__file__", str(tmp_path / "device_FL_MCP_Bridge.py"))
    monkeypatch.delenv("FL_MCP_FL_STUDIO_BRIDGE_LOG", raising=False)

    module._log("quiet by default")

    assert not (tmp_path / "fl_mcp_bridge.log").exists()

    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_LOG", "1")
    module._log("enabled")

    assert "enabled" in (tmp_path / "fl_mcp_bridge.log").read_text(encoding="utf-8")


def test_fl_controller_script_poll_status_includes_runtime_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", str(tmp_path))
    cast(Any, module)._last_status_at = 0.0
    cast(Any, module)._processed_request_count = 7
    cast(Any, module)._last_bridge_error = "api_missing: unavailable"

    module._poll("test", force=True)

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "ready"
    assert status["message"] == "FL MCP Bridge MIDI script polling."
    assert status["poll_reason"] == "test"
    assert status["processed_request_count"] == 7
    assert status["processed_request"] is False
    assert status["last_error"] == "api_missing: unavailable"
    assert isinstance(status["last_poll_at"], float)


def test_fl_controller_script_extra_callbacks_delegate_to_poller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    calls: list[tuple[str, bool]] = []

    def poll(reason: str, *, force: bool = False) -> None:
        calls.append((reason, force))

    monkeypatch.setattr(module, "_poll", poll)

    module.OnIdle()
    module.OnRefresh(1)
    module.OnUpdateBeatIndicator(1)
    module.OnDirtyMixerTrack(2)
    module.OnMidiMsg(SimpleNamespace(handled=False))

    assert calls == [
        ("idle", False),
        ("refresh", False),
        ("beat", False),
        ("mixer", False),
        ("midi", False),
    ]


def test_fl_controller_script_poll_rate_limit_and_heartbeat_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monotonic_now = {"value": 100.0}
    wall_now = {"value": 1000.0}
    process_calls: list[str] = []
    status_writes: list[tuple[str, bool]] = []

    def process_one_request() -> bool:
        process_calls.append("processed")
        return False

    def write_poll_status(reason: str, *, processed: bool) -> None:
        status_writes.append((reason, processed))

    monkeypatch.setattr(module.time, "monotonic", lambda: monotonic_now["value"])
    monkeypatch.setattr(module.time, "time", lambda: wall_now["value"])
    monkeypatch.setattr(module, "_process_one_request", process_one_request)
    monkeypatch.setattr(module, "_write_poll_status", write_poll_status)

    module._poll("idle", force=True)

    assert len(process_calls) == 1
    assert status_writes == [("idle", False)]

    monotonic_now["value"] += module.MIN_POLL_INTERVAL_SECONDS / 2
    wall_now["value"] += 0.1
    module._poll("idle")

    assert len(process_calls) == 1
    assert status_writes == [("idle", False)]

    monotonic_now["value"] += module.MIN_POLL_INTERVAL_SECONDS * 2
    wall_now["value"] = 1000.0 + module.STATUS_HEARTBEAT_INTERVAL_SECONDS - 0.1
    module._poll("idle")

    assert len(process_calls) == 2
    assert status_writes == [("idle", False)]

    monotonic_now["value"] += module.MIN_POLL_INTERVAL_SECONDS * 2
    wall_now["value"] = 1000.0 + module.STATUS_HEARTBEAT_INTERVAL_SECONDS + 0.1
    module._poll("idle")

    assert len(process_calls) == 3
    assert status_writes == [("idle", False), ("idle", False)]


def test_fl_controller_script_defaults_bridge_dir_next_to_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.delenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", raising=False)

    bridge_dir = Path(module._bridge_dir())

    assert bridge_dir == Path(cast(str, module.__file__)).resolve().parent / "bridge"


def test_fl_controller_script_allows_default_bridge_when_host_stat_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.delenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", raising=False)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "device_FL_MCP_Bridge.py"))

    def fail_host_stat(*_args: object, **_kwargs: object) -> object:
        raise SystemError("error return without exception set")

    with pytest.MonkeyPatch.context() as host_monkeypatch:
        host_monkeypatch.setattr(module.os, "name", "posix")
        host_monkeypatch.setattr(module.os, "stat", fail_host_stat)
        bridge_dir = module._bridge_dir()

        assert module._ensure_private_bridge_dir(bridge_dir) == bridge_dir


def test_fl_controller_script_keeps_env_bridge_dir_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", str(tmp_path / "bridge"))

    def fail_host_stat(*_args: object, **_kwargs: object) -> object:
        raise SystemError("error return without exception set")

    with pytest.MonkeyPatch.context() as host_monkeypatch:
        host_monkeypatch.setattr(module.os, "name", "posix")
        host_monkeypatch.setattr(module.os, "stat", fail_host_stat)

        with pytest.raises(SystemError, match="error return"):
            module._ensure_private_bridge_dir(module._bridge_dir())


def test_fl_controller_script_deduplicates_processed_request_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_controller_script()
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_DIR", str(tmp_path))
    cast(Any, module)._processed_request_paths.clear()
    calls = {"count": 0}

    def handle_request(request: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        return {
            "success": True,
            "message": "ok",
            "provider": request.get("provider") or "flapi-live",
            "result": {"calls": calls["count"]},
        }

    monkeypatch.setattr(module, "_handle_request", handle_request)
    request_path = tmp_path / "request-live.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "live",
                "request": {
                    "domain": "transport",
                    "operation": "get_tempo",
                    "provider": "flapi-live",
                    "payload": {},
                },
            }
        ),
        encoding="utf-8",
    )

    assert module._process_one_request() is True
    assert module._process_one_request() is False

    response = json.loads((tmp_path / "response-live.json").read_text(encoding="utf-8"))
    assert response["result"]["calls"] == 1
    assert calls["count"] == 1
    assert request_path.exists()


def test_fl_controller_script_handles_transport_read_and_mutation() -> None:
    module = _load_controller_script()
    tempo_state = {"tempo": 120.0}

    def get_current_tempo() -> float:
        return tempo_state["tempo"]

    def set_current_tempo(tempo: float) -> None:
        tempo_state["tempo"] = tempo

    fake_transport = SimpleNamespace(
        getCurrentTempo=get_current_tempo,
        setCurrentTempo=set_current_tempo,
        isPlaying=lambda: False,
    )
    dynamic_module = cast(Any, module)
    dynamic_module.transport = fake_transport
    dynamic_module.mixer = None

    mutation = module._handle_request(
        {
            "domain": "transport",
            "operation": "set_tempo",
            "provider": "flapi-live",
            "payload": {"bpm": 132},
        }
    )
    read = module._handle_request(
        {"domain": "transport", "operation": "get_state", "provider": "flapi-live"}
    )

    assert mutation["success"] is True
    assert mutation["result"]["tempo"] == 132.0
    assert read["success"] is True
    assert read["result"]["tempo"] == 132.0


def test_fl_controller_script_uses_mixer_tempo_fallback() -> None:
    module = _load_controller_script()
    tempo_state = {"tempo": 120000.0}

    def get_current_tempo(_mode: int = 0) -> float:
        return tempo_state["tempo"]

    def set_current_tempo(tempo: float, _mode: int = 0) -> None:
        tempo_state["tempo"] = tempo

    fake_transport = SimpleNamespace(isPlaying=lambda: False)
    fake_mixer = SimpleNamespace(
        getCurrentTempo=get_current_tempo,
        setCurrentTempo=set_current_tempo,
    )
    dynamic_module = cast(Any, module)
    dynamic_module.transport = fake_transport
    dynamic_module.mixer = fake_mixer

    mutation = module._handle_request(
        {
            "domain": "transport",
            "operation": "set_tempo",
            "provider": "flapi-live",
            "payload": {"bpm": 126},
        }
    )
    read = module._handle_request(
        {"domain": "transport", "operation": "get_tempo", "provider": "flapi-live"}
    )

    assert mutation["success"] is True
    assert mutation["result"]["tempo"] == 126.0
    assert tempo_state["tempo"] == 126000.0
    assert read["success"] is True
    assert read["result"]["tempo"] == 126.0


def test_fl_controller_script_has_adapter_record_for_every_catalog_operation() -> None:
    module = _load_controller_script()

    for spec in FL_TOOL_SPECS:
        record = module.bridge_adapter_record(spec.domain, spec.operation)
        assert record["operation_id"] == f"{spec.domain}.{spec.operation}"
        assert record["callable_candidates"]
        assert record["failure_code"] == "api_missing"


def test_fl_controller_script_missing_api_returns_structured_failure() -> None:
    module = _load_controller_script()
    response = module._handle_request(
        {
            "domain": "automation",
            "operation": "create_clip",
            "provider": "flapi-live",
            "payload": {"name": "Filter Sweep"},
        }
    )

    assert response["success"] is False
    assert response["error_code"] == "api_missing"
    assert response["result"]["operation_id"] == "automation.create_clip"
    assert response["result"]["attempted_modules"]
    assert response["result"]["attempted_functions"]
    assert "remediation" in response["result"]


def test_fl_controller_script_rejected_payload_returns_structured_failure() -> None:
    module = _load_controller_script()
    dynamic_module = cast(Any, module)
    dynamic_module.mixer = SimpleNamespace(
        setTrackVolume=lambda track, value, mode: None,
    )

    response = module._handle_request(
        {
            "domain": "mixer",
            "operation": "set_track_volume",
            "provider": "flapi-live",
            "payload": {"track_index": 1, "volume": 0.5},
        }
    )

    assert response["success"] is False
    assert response["error_code"] == "unsupported_host_behavior"
    assert response["result"]["operation_id"] == "mixer.set_track_volume"
    assert "mixer.setTrackVolume" in response["result"]["attempted_functions"]
    assert "remediation" in response["result"]


def test_live_controller_bridge_uses_mixer_tempo_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tempo_state = {"tempo": 120000.0}

    def get_current_tempo(_mode: int = 0) -> float:
        return tempo_state["tempo"]

    def set_current_tempo(tempo: float, _mode: int = 0) -> None:
        tempo_state["tempo"] = tempo

    fake_transport = SimpleNamespace()
    fake_mixer = SimpleNamespace(
        getCurrentTempo=get_current_tempo,
        setCurrentTempo=set_current_tempo,
    )
    monkeypatch.setitem(sys.modules, "transport", fake_transport)
    monkeypatch.setitem(sys.modules, "mixer", fake_mixer)

    mutation = controller_bridge.handle_request(
        BridgeLiveRequest(
            domain="transport",
            operation="set_tempo",
            provider="flapi-live",
            payload={"bpm": 127},
        )
    )
    read = controller_bridge.handle_request(
        BridgeLiveRequest(domain="transport", operation="get_tempo", provider="flapi-live")
    )

    assert mutation["success"] is True
    assert mutation["result"]["tempo"] == 127.0
    assert tempo_state["tempo"] == 127000.0
    assert read["success"] is True
    assert read["result"]["tempo"] == 127.0
