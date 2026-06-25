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
from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.tools.public import apply_changes, plan_changes
from fl_mcp.transactions.apply import apply_changes as apply_engine
from fl_mcp.transactions.planner import plan_changes as plan_engine


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