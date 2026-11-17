"""Unit tests for safety_mode enforcement."""

from __future__ import annotations

import pytest

from fl_mcp.config.settings import settings
from fl_mcp.middleware.safety import (
    SafetyModeError,
    effective_safety_mode,
    enforce_operation_safety_mode,
    enforce_safety_mode,
    ensure_safe_mode,
)
from fl_mcp.operations import find_operation_for_change, list_operation_specs
from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.tools.public import apply_changes, plan_changes
from fl_mcp.transactions.apply import apply_changes as apply_engine
from fl_mcp.transactions.planner import plan_changes as plan_engine

_CATALOG_DESTRUCTIVE_IDS = {
    "automation.delete_clip",
    "automation.write_points",
    "general.close_project",
    "general.new_project",
    "general.open_project",
    "general.redo",
    "general.restore_undo",
    "general.undo",
    "piano-roll.clear",
    "piano-roll.delete_notes",
    "playlist.delete_clip",
    "playlist.delete_marker",
    "plugins.replace",
}


def _envelope(
    *,
    safety_mode: str = "standard",
    changes: list[DomainChange] | None = None,
    mode: str = "preview",
) -> TransactionEnvelope:
    return TransactionEnvelope(
        request_id="safety-test",
        mode=mode,  # type: ignore[arg-type]
        safety_mode=safety_mode,  # type: ignore[arg-type]
        changes=changes
        or [
            DomainChange(
                domain="transport",
                operation="set_tempo",
                rollback_class="best_effort",
                payload={"bpm": 128.0},
            )
        ],
    )


def test_ensure_safe_mode_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported safety mode"):
        ensure_safe_mode("permissive")


def test_enforce_safety_mode_rejects_relaxed() -> None:
    envelope = _envelope(safety_mode="relaxed")
    with pytest.raises(SafetyModeError, match=r"relaxed.*not supported"):
        enforce_safety_mode(envelope.safety_mode, envelope.changes)


def test_enforce_safety_mode_allows_standard() -> None:
    envelope = _envelope(safety_mode="standard")
    enforce_safety_mode(envelope.safety_mode, envelope.changes)


def test_effective_safety_mode_prefers_strict() -> None:
    assert effective_safety_mode("standard", "strict") == "strict"
    assert effective_safety_mode("strict", "standard") == "strict"
    assert effective_safety_mode("relaxed", "strict") == "strict"
    assert effective_safety_mode("standard", "standard") == "standard"


def test_enforce_operation_safety_mode_blocks_destructive_in_strict() -> None:
    with pytest.raises(SafetyModeError, match=r"strict.*blocks destructive"):
        enforce_operation_safety_mode("strict", "playlist.delete_clip")


@pytest.mark.parametrize(
    "operation_id",
    [
        "piano-roll.delete_notes",
        "plugins.replace",
        "general.open_project",
        "general.undo",
        "general.redo",
        "general.restore_undo",
        "automation.write_points",
    ],
)
def test_strict_mode_blocks_delete_replace_open_and_undo(operation_id: str) -> None:
    spec = find_operation_for_change(*operation_id.split(".", 1))
    assert spec is not None
    assert spec.destructive is True
    assert spec.rollback_class is not None
    change = DomainChange(
        domain=spec.domain,
        operation=spec.operation,
        rollback_class=spec.rollback_class,
    )
    with pytest.raises(SafetyModeError, match=r"strict.*blocks destructive"):
        enforce_operation_safety_mode("strict", operation_id)
    with pytest.raises(SafetyModeError, match=r"strict.*blocks destructive"):
        enforce_safety_mode("strict", [change])
    enforce_operation_safety_mode("standard", operation_id)
    enforce_safety_mode("standard", [change])


def test_catalog_destructive_ids_are_limited_to_declared_operations() -> None:
    destructive = {
        f"{spec.domain}.{spec.operation}" for spec in list_operation_specs() if spec.destructive
    }
    assert destructive == _CATALOG_DESTRUCTIVE_IDS


def test_strict_mode_allows_non_destructive_transport_set_tempo() -> None:
    spec = find_operation_for_change("transport", "set_tempo")
    assert spec is not None
    assert spec.destructive is False
    assert spec.rollback_class is not None
    enforce_operation_safety_mode("strict", "transport.set_tempo")
    enforce_safety_mode(
        "strict",
        [
            DomainChange(
                domain="transport",
                operation="set_tempo",
                rollback_class=spec.rollback_class,
                payload={"bpm": 128.0},
            )
        ],
    )


def test_enforce_operation_safety_mode_blocks_unknown_in_strict() -> None:
    with pytest.raises(SafetyModeError, match=r"strict.*blocks unknown"):
        enforce_operation_safety_mode("strict", "unknown.operation")


def test_enforce_operation_safety_mode_allows_destructive_in_standard() -> None:
    enforce_operation_safety_mode("standard", "playlist.delete_clip")


def test_enforce_safety_mode_blocks_destructive_in_strict() -> None:
    envelope = _envelope(
        safety_mode="strict",
        changes=[
            DomainChange(
                domain="playlist",
                operation="delete_clip",
                rollback_class="checkpointed",
                payload={"track_index": 0, "clip_index": 0},
            )
        ],
    )
    with pytest.raises(SafetyModeError, match=r"strict.*blocks destructive"):
        enforce_safety_mode(envelope.safety_mode, envelope.changes)


def test_enforce_safety_mode_blocks_unknown_change_in_strict() -> None:
    envelope = _envelope(
        safety_mode="strict",
        changes=[
            DomainChange(
                domain="custom",
                operation="unknown_op",
                rollback_class="best_effort",
                payload={},
            )
        ],
    )
    with pytest.raises(SafetyModeError, match=r"strict.*blocks destructive or unknown"):
        enforce_safety_mode(envelope.safety_mode, envelope.changes)


def test_plan_engine_honors_server_strict_over_envelope_standard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "safety_mode", "strict")
    with pytest.raises(SafetyModeError, match="strict"):
        plan_engine(
            _envelope(
                safety_mode="standard",
                changes=[
                    DomainChange(
                        domain="playlist",
                        operation="delete_clip",
                        rollback_class="checkpointed",
                        payload={"track_index": 0, "clip_index": 0},
                    )
                ],
            )
        )


def test_plan_changes_rejects_relaxed_mode() -> None:
    result = plan_changes(_envelope(safety_mode="relaxed"))
    assert result["status"] == "error"
    assert "relaxed" in str(result["error"]).lower()


def test_apply_changes_rejects_relaxed_mode() -> None:
    result = apply_changes(_envelope(safety_mode="relaxed", mode="apply"))
    assert result["status"] == "error"
    assert "relaxed" in str(result["error"]).lower()


def test_plan_engine_blocks_strict_destructive_changes() -> None:
    with pytest.raises(SafetyModeError, match="strict"):
        plan_engine(
            _envelope(
                safety_mode="strict",
                changes=[
                    DomainChange(
                        domain="playlist",
                        operation="delete_clip",
                        rollback_class="checkpointed",
                        payload={"track_index": 0, "clip_index": 0},
                    )
                ],
            )
        )


def test_apply_engine_blocks_strict_destructive_changes() -> None:
    with pytest.raises(SafetyModeError, match="strict"):
        apply_engine(
            _envelope(
                safety_mode="strict",
                mode="apply",
                changes=[
                    DomainChange(
                        domain="playlist",
                        operation="delete_clip",
                        rollback_class="checkpointed",
                        payload={"track_index": 0, "clip_index": 0},
                    )
                ],
            )
        )