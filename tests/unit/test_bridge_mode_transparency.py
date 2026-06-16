"""Tests that bridge_mode is surfaced in all tool response paths."""

from __future__ import annotations

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE


def test_bridge_mode_on_read_result() -> None:
    """Read operations must include bridge_mode='mock' in their result."""
    result = DEFAULT_BRIDGE.execute_operation(
        domain="transport",
        operation="get_state",
        payload={},
    )
    assert result.bridge_mode == "mock"
    assert result.success is True


def test_bridge_mode_on_transaction_result() -> None:
    """Transaction operations must include bridge_mode='mock' in their result."""
    result = DEFAULT_BRIDGE.execute_operation(
        domain="transport",
        operation="set_tempo",
        payload={"tempo": 120.0},
    )
    assert result.bridge_mode == "mock"
    assert result.success is True


def test_mock_mode_warning_in_response_payload() -> None:
    """Mock bridge responses include mock_mode_warning."""
    from fl_mcp.tools.fl_surface import FL_TOOL_BY_NAME, FL_TOOL_HANDLERS

    handler = FL_TOOL_HANDLERS.get("transport_get_state")
    assert handler is not None, "transport_get_state handler not found"
    spec = FL_TOOL_BY_NAME["transport_get_state"]
    request = spec.request_model.model_validate({})
    result = handler(request)
    assert "bridge_mode" in result, "bridge_mode missing from tool response"
    assert result["bridge_mode"] == "mock"
    assert "mock_mode_warning" in result, "mock_mode_warning missing from mock response"


def test_bridge_mode_from_environment_defaults_to_mock() -> None:
    """Default bridge (no env vars) runs in mock mode."""
    assert DEFAULT_BRIDGE.mode == "mock"
