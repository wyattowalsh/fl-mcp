"""Tests for FLStudioBridge mock execution paths."""

from __future__ import annotations

import subprocess

import pytest

from fl_mcp.bridge.bundle import bridge_runner_command
from fl_mcp.bridge.fl_studio import (
    DEFAULT_BRIDGE,
    DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS,
    BridgeExecutionResult,
    FLStudioBridge,
)
from fl_mcp.bridge.host_client import DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS
from fl_mcp.bridge.selected_controller_client import DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS

# ---------------------------------------------------------------------------
# 1. Bridge construction
# ---------------------------------------------------------------------------


def test_mock_mode_bridge_construction() -> None:
    bridge = FLStudioBridge(mode="mock")
    assert bridge.mode == "mock"


def test_live_mode_bridge_construction() -> None:
    bridge = FLStudioBridge(mode="live", live_command="/usr/bin/echo")
    assert bridge.mode == "live"


def test_outer_live_timeout_exceeds_actual_app_client_timeouts() -> None:
    assert DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS > DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS
    assert DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS > DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS


def test_live_mode_mock_provider_uses_mock_backend_without_subprocess() -> None:
    bridge = FLStudioBridge(mode="live", live_command="/usr/bin/false")

    result = bridge.execute_operation(
        domain="render",
        operation="export",
        payload={"output_path": "mix.wav"},
        provider="mock",
    )

    assert result.success is True
    assert result.bridge_mode == "mock"
    assert result.provider == "mock"
    assert result.result["output_path"] == "mix.wav"


# ---------------------------------------------------------------------------
# 2. Transport domain — get_state
# ---------------------------------------------------------------------------


def test_execute_transport_get_state_returns_success() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="get_state", payload={})
    assert isinstance(result, BridgeExecutionResult)
    assert result.success is True
    assert result.domain == "transport"
    assert result.operation == "get_state"
    assert result.bridge_mode == "mock"
    assert isinstance(result.result, dict)


def test_execute_transport_get_state_contains_status_fields() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="get_state", payload={})
    # The mock generator for transport.get_state returns playing/recording/tempo etc.
    assert result.success
    assert isinstance(result.result, dict)
    assert "playing" in result.result or "tempo" in result.result


# ---------------------------------------------------------------------------
# 3. Channels domain — list
# ---------------------------------------------------------------------------


def test_execute_channels_list_returns_success() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="channels", operation="list", payload={})
    assert isinstance(result, BridgeExecutionResult)
    assert result.success is True
    assert result.domain == "channels"
    assert result.operation == "list"
    assert isinstance(result.result, dict)


def test_execute_channels_list_result_has_data() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="channels", operation="list", payload={})
    # Should contain channel-related data from the mock generator.
    assert len(result.result) > 0


# ---------------------------------------------------------------------------
# 4. Unknown domain / unsupported operation — fallback behaviour
# ---------------------------------------------------------------------------


def test_unknown_domain_returns_failure() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="unknown_domain", operation="unknown_op", payload={})
    assert result.success is False
    assert result.error_code == "unsupported_domain"
    assert "unknown_domain" in result.message


def test_unsupported_operation_in_valid_domain_returns_failure() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="nonexistent_op", payload={})
    assert result.success is False
    assert result.error_code == "unsupported_operation"


def test_noop_operation_always_succeeds() -> None:
    """The mock supports 'noop' for any domain."""
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="noop", payload={})
    assert result.success is True


# ---------------------------------------------------------------------------
# 5. Empty domain / operation strings
# ---------------------------------------------------------------------------


def test_empty_domain_returns_error() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="", operation="get_state", payload={})
    # Empty string is not in DOMAINS, so the bridge returns unsupported_domain.
    assert result.success is False
    assert result.error_code == "unsupported_domain"


def test_empty_operation_returns_error() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="", payload={})
    # Empty operation string is not in the supported set → unsupported_operation.
    assert result.success is False
    assert result.error_code == "unsupported_operation"


# ---------------------------------------------------------------------------
# 6. Result is always a dict with known structure
# ---------------------------------------------------------------------------


def test_result_is_always_dict() -> None:
    bridge = FLStudioBridge(mode="mock")
    for domain, operation in [
        ("transport", "get_state"),
        ("channels", "list"),
        ("mixer", "list_tracks"),
        ("patterns", "list"),
    ]:
        result = bridge.execute_operation(domain=domain, operation=operation, payload={})
        assert isinstance(result.result, dict), (
            f"Expected dict for {domain}.{operation}, got {type(result.result)}"
        )


def test_bridge_execution_result_fields_populated() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="mixer", operation="list_tracks", payload={})
    assert result.domain == "mixer"
    assert result.operation == "list_tracks"
    assert result.bridge_mode == "mock"
    assert result.provider is not None
    assert result.execution_id is not None
    assert result.error_code is None  # success case


def test_execution_id_is_stable_for_same_input() -> None:
    bridge = FLStudioBridge(mode="mock")
    r1 = bridge.execute_operation(domain="transport", operation="get_tempo", payload={})
    r2 = bridge.execute_operation(domain="transport", operation="get_tempo", payload={})
    assert r1.execution_id == r2.execution_id
    assert r1.execution_id is not None


def test_execution_id_differs_for_different_payload() -> None:
    bridge = FLStudioBridge(mode="mock")
    r1 = bridge.execute_operation(domain="transport", operation="set_tempo", payload={"bpm": 120})
    r2 = bridge.execute_operation(domain="transport", operation="set_tempo", payload={"bpm": 140})
    assert r1.execution_id != r2.execution_id


# ---------------------------------------------------------------------------
# 7. DEFAULT_BRIDGE singleton
# ---------------------------------------------------------------------------


def test_default_bridge_importable_and_has_mode() -> None:
    assert hasattr(DEFAULT_BRIDGE, "mode")
    # When run without FL_MCP_BRIDGE_MODE env var, default is "mock".
    assert DEFAULT_BRIDGE.mode in ("mock", "live")


def test_default_bridge_is_fl_studio_bridge_instance() -> None:
    assert isinstance(DEFAULT_BRIDGE, FLStudioBridge)


# ---------------------------------------------------------------------------
# 8. Force-fail via payload flag
# ---------------------------------------------------------------------------


def test_force_fail_payload_triggers_mock_failure() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(
        domain="transport",
        operation="get_state",
        payload={"force_fail": True},
    )
    assert result.success is False
    assert result.error_code == "mock_forced_failure"


def test_fail_prefixed_operation_triggers_mock_failure() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(
        domain="transport",
        operation="fail_something",
        payload={},
    )
    assert result.success is False
    assert result.error_code == "mock_forced_failure"


# ---------------------------------------------------------------------------
# 9. Provider resolution in mock mode
# ---------------------------------------------------------------------------


def test_mock_mode_resolves_provider_to_mock() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(domain="transport", operation="get_state", payload={})
    assert result.provider == "mock"


def test_explicit_non_mock_provider_fails_closed_in_mock_mode() -> None:
    bridge = FLStudioBridge(mode="mock")
    result = bridge.execute_operation(
        domain="transport",
        operation="get_state",
        payload={},
        provider="flapi-live",
    )
    assert result.provider == "flapi-live"
    assert result.success is False
    assert result.bridge_mode == "mock"
    assert result.error_code == "live_provider_unavailable"


def test_live_nonzero_exit_preserves_structured_bridge_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _run_with_structured_error(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command = args[0]
        return subprocess.CompletedProcess(
            args=command,
            returncode=2,
            stdout=(
                '{"success": false, "message": "No callable", '
                '"error_code": "api_missing", "execution_id": "bridge-1", '
                '"provider": "flapi-live", '
                '"result": {"operation_id": "automation.create_clip"}}'
            ),
            stderr="host stderr",
        )

    monkeypatch.setattr(subprocess, "run", _run_with_structured_error)
    bridge = FLStudioBridge(mode="live", live_command="bridge-runner")

    result = bridge.execute_operation(
        domain="automation",
        operation="create_clip",
        payload={"name": "Filter Sweep"},
        provider="flapi-live",
    )

    assert result.success is False
    assert result.error_code == "api_missing"
    assert result.execution_id == "bridge-1"
    assert result.provider == "flapi-live"
    assert result.result["operation_id"] == "automation.create_clip"
    assert result.result["bridge_returncode"] == 2


def test_live_harness_bridge_command_executes_read_and_mutation() -> None:
    bridge = FLStudioBridge(mode="live", live_command=bridge_runner_command(harness=True))

    read_result = bridge.execute_operation(
        domain="transport",
        operation="get_state",
        payload={},
        provider="flapi-live",
    )
    mutation_result = bridge.execute_operation(
        domain="transport",
        operation="set_tempo",
        payload={"bpm": 120.0},
        provider="flapi-live",
    )

    assert read_result.success is True
    assert read_result.bridge_mode == "live"
    assert read_result.provider == "flapi-live"
    assert mutation_result.success is True
    assert mutation_result.bridge_mode == "live"
    assert mutation_result.provider == "flapi-live"
