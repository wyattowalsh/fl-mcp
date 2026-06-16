"""Tests for the operations compatibility facade (fl_mcp.operations)."""

from __future__ import annotations

import pytest

from fl_mcp.operations import (
    OperationPayloadValidationError,
    OperationSpec,
    build_operation_tool_handlers,
    execute_operation_tool,
    find_operation_for_change,
    get_operation_spec,
    list_operation_specs,
    validate_change,
)
from fl_mcp.schemas import DomainChange

# ---------------------------------------------------------------------------
# list_operation_specs
# ---------------------------------------------------------------------------


def test_list_operation_specs_returns_non_empty_tuple() -> None:
    specs = list_operation_specs()
    assert isinstance(specs, tuple)
    assert len(specs) > 0


def test_list_operation_specs_entries_have_expected_attributes() -> None:
    specs = list_operation_specs()
    for spec in specs:
        assert isinstance(spec, OperationSpec)
        assert spec.name
        assert spec.domain
        assert spec.operation
        assert spec.description
        assert spec.request_model is not None
        assert isinstance(spec.tags, tuple)
        assert isinstance(spec.read_only, bool)
        assert isinstance(spec.destructive, bool)
        assert isinstance(spec.idempotent, bool)
        assert isinstance(spec.task, bool)


# ---------------------------------------------------------------------------
# get_operation_spec
# ---------------------------------------------------------------------------


def test_get_operation_spec_known_tool() -> None:
    spec = get_operation_spec("transport_get_state")
    assert isinstance(spec, OperationSpec)
    assert spec.name == "transport_get_state"
    assert spec.domain == "transport"
    assert spec.operation == "get_state"


def test_get_operation_spec_nonexistent_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown FL operation tool"):
        get_operation_spec("nonexistent_nope")


# ---------------------------------------------------------------------------
# find_operation_for_change
# ---------------------------------------------------------------------------


def test_find_operation_for_change_valid_domain_operation() -> None:
    spec = find_operation_for_change("transport", "get_state")
    assert spec is not None
    assert isinstance(spec, OperationSpec)
    assert spec.domain == "transport"
    assert spec.operation == "get_state"


def test_find_operation_for_change_unknown_domain_returns_none() -> None:
    result = find_operation_for_change("nonexistent", "nope")
    assert result is None


def test_find_operation_for_change_resolves_alias() -> None:
    spec = find_operation_for_change("channels", "list")
    assert spec is not None
    assert spec.domain == "channels"
    assert spec.operation == "list_channels"


# ---------------------------------------------------------------------------
# build_operation_tool_handlers
# ---------------------------------------------------------------------------


def test_build_operation_tool_handlers_returns_dict_with_known_names() -> None:
    handlers = build_operation_tool_handlers()
    assert isinstance(handlers, dict)
    assert len(handlers) > 0
    assert "transport_get_state" in handlers
    assert "mixer_list_tracks" in handlers
    assert callable(handlers["transport_get_state"])


# ---------------------------------------------------------------------------
# validate_change
# ---------------------------------------------------------------------------


def test_validate_change_valid_change_returns_spec_and_normalized_change() -> None:
    change = DomainChange(
        domain="transport",
        operation="get_state",
        rollback_class="best_effort",
    )
    spec, normalized = validate_change(change)
    assert spec is not None
    assert isinstance(spec, OperationSpec)
    assert spec.domain == "transport"
    assert normalized.domain == "transport"
    assert normalized.operation == "get_state"


def test_validate_change_unsupported_domain_returns_none_spec() -> None:
    change = DomainChange(
        domain="nonexistent",
        operation="nope",
        rollback_class="best_effort",
    )
    spec, returned_change = validate_change(change)
    assert spec is None
    assert returned_change is change


def test_validate_change_applies_alias_normalization() -> None:
    change = DomainChange(
        domain="channels",
        operation="list",
        rollback_class="best_effort",
    )
    spec, normalized = validate_change(change)
    assert spec is not None
    assert normalized.domain == "channels"
    assert normalized.operation == "list_channels"


def test_validate_change_populates_rollback_class_from_spec() -> None:
    change = DomainChange(
        domain="transport",
        operation="set_tempo",
        rollback_class="best_effort",
        payload={"bpm": 120.0},
    )
    spec, normalized = validate_change(change)
    assert spec is not None
    if spec.rollback_class is not None:
        assert normalized.rollback_class == spec.rollback_class


def test_validate_change_fails_closed_for_invalid_known_payload() -> None:
    change = DomainChange(
        domain="transport",
        operation="set_tempo",
        rollback_class="checkpointed",
        payload={},
    )

    with pytest.raises(OperationPayloadValidationError) as exc_info:
        validate_change(change)

    assert exc_info.value.domain == "transport"
    assert exc_info.value.operation == "set_tempo"
    assert "bpm" in str(exc_info.value)


# ---------------------------------------------------------------------------
# execute_operation_tool
# ---------------------------------------------------------------------------


def test_execute_operation_tool_valid_request_returns_dict() -> None:
    result = execute_operation_tool("transport_get_state")
    assert isinstance(result, dict)
    assert "status" in result
    assert "domain" in result
    assert result["domain"] == "transport"
    assert result["operation"] == "get_state"


def test_execute_operation_tool_with_dict_request() -> None:
    result = execute_operation_tool("transport_get_state", {})
    assert isinstance(result, dict)
    assert result["status"] == "ok"


def test_execute_operation_tool_unknown_name_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown FL operation tool"):
        execute_operation_tool("nonexistent_nope")
