"""Rollback policy must not claim the server reverted a change."""

from __future__ import annotations

import pytest

from fl_mcp.bridge.fl_studio import BridgeExecutionResult
from fl_mcp.schemas import DomainChange, RollbackClass, TransactionEnvelope
from fl_mcp.transactions.apply import apply_changes
from fl_mcp.transactions.rollback import (
    ROLLBACK_POLICY_BY_CLASSIFICATION,
    classify_execution_failure,
    rollback_policy_for,
)

_NOT_REVERTED = "All-or-nothing transaction failed. The server did not revert earlier changes."


def test_transactional_classes_do_not_support_automatic_rollback() -> None:
    fully = rollback_policy_for("fully_transactional")
    checkpointed = rollback_policy_for("checkpointed")

    assert fully.supports_automatic_rollback is False
    assert fully.requires_checkpoint is False
    assert "automatically" not in fully.description.lower()
    assert "does not revert" in fully.description

    assert checkpointed.supports_automatic_rollback is False
    assert checkpointed.requires_checkpoint is True
    assert "automatically" not in checkpointed.description.lower()
    assert "does not revert" in checkpointed.description


def test_classify_execution_failure_skips_rolled_back_status() -> None:
    expected: dict[RollbackClass, str] = {
        "fully_transactional": "failed_manual_intervention",
        "checkpointed": "failed_checkpoint_required",
        "best_effort": "failed_manual_intervention",
        "unsafe_raw": "failed_checkpoint_required",
    }

    for classification, status in expected.items():
        policy = ROLLBACK_POLICY_BY_CLASSIFICATION[classification]
        assert policy.supports_automatic_rollback is False
        assert classify_execution_failure(classification) == status
        assert status != "failed_rolled_back"


def test_all_or_nothing_failure_does_not_call_undo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def _execute(change: DomainChange) -> BridgeExecutionResult:
        calls.append((change.domain, change.operation))
        failed = change.operation == "fail_start"
        return BridgeExecutionResult(
            domain=change.domain,
            operation=change.operation,
            success=not failed,
            message="mock failure" if failed else "mock applied",
            error_code="mock_forced_failure" if failed else None,
            execution_id="exec-1",
            bridge_mode="mock",
            provider=change.provider or "mock",
            result={},
        )

    monkeypatch.setattr("fl_mcp.transactions.apply.execute_change", _execute)
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "rollback-honesty",
            "mode": "apply",
            "execution_policy": "all-or-nothing",
            "changes": [
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "checkpointed",
                    "payload": {},
                },
                {
                    "domain": "transport",
                    "operation": "fail_start",
                    "rollback_class": "fully_transactional",
                    "payload": {},
                },
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert calls == [("mixer", "set_volume"), ("transport", "fail_start")]
    assert result.status == "failed"
    assert result.rollback_capability == "partial"
    assert isinstance(reports, list)
    assert reports[0]["message"] == _NOT_REVERTED
    assert "was reverted" not in reports[0]["message"]
    assert reports[0]["execution_id"] is None
    assert reports[1]["message"] == "mock failure"
    assert result.per_domain_results["mixer"] == "failed_checkpoint_required"
    assert result.per_domain_results["transport"] == "failed_manual_intervention"
    assert "failed_rolled_back" not in result.per_domain_results.values()
