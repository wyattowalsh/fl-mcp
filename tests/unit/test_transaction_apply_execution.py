from __future__ import annotations

import subprocess

import pytest

from fl_mcp.bridge.fl_studio import (
    DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS,
    FLStudioBridge,
)
from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.transactions.apply import apply_changes


def _build_envelope(
    *,
    mode: str = "apply",
    execution_policy: str = "all-or-nothing",
) -> TransactionEnvelope:
    return TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-1",
            "mode": mode,
            "execution_policy": execution_policy,
            "target_snapshot_id": "snap-before",
            "changes": [
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "checkpointed",
                },
                {
                    "domain": "mixer",
                    "operation": "set_pan",
                    "rollback_class": "best_effort",
                },
                {
                    "domain": "patterns",
                    "operation": "set_length",
                    "rollback_class": "fully_transactional",
                },
            ],
        }
    )


def test_apply_changes_preview_mode_returns_planned_result() -> None:
    envelope = _build_envelope(mode="preview")
    result = apply_changes(envelope)

    assert result.status == "planned"
    assert result.transaction_id.startswith("tx-")
    assert set(result.per_domain_results.values()) == {"planned"}
    assert result.diff_summary["mode"] == "preview"


def test_apply_changes_preserves_multiple_domain_results_without_overwrite() -> None:
    envelope = _build_envelope(mode="apply")
    result = apply_changes(envelope)

    assert "mixer#1" in result.per_domain_results
    assert "mixer#2" in result.per_domain_results
    assert "patterns" in result.per_domain_results


def test_apply_changes_allow_partial_returns_partially_applied_on_mixed_results() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-2",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "checkpointed",
                    "payload": {},
                },
                {
                    "domain": "mixer",
                    "operation": "fail_volume",
                    "rollback_class": "best_effort",
                    "payload": {},
                },
            ],
        }
    )

    result = apply_changes(envelope)

    assert result.status == "partially_applied"
    assert result.diff_summary["failed_count"] == 1
    assert result.warnings


def test_apply_changes_all_or_nothing_fails_when_any_change_fails() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-3",
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
    assert result.status == "failed"
    assert result.checkpoint_id is None
    assert result.diff_summary["applied_count"] == 0
    assert "applied" not in set(result.per_domain_results.values())
    reports = result.diff_summary["reports"]
    assert isinstance(reports, list)
    assert all(report["success"] is False for report in reports)
    assert result.errors


def test_apply_changes_reports_unsupported_domain_with_error_taxonomy() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-4",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "unknown-domain",
                    "operation": "noop",
                    "rollback_class": "unsafe_raw",
                    "payload": {},
                }
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert isinstance(reports, list)
    assert reports[0]["error_code"] == "unsupported_domain"
    assert result.per_domain_results["unknown-domain"] == "failed_checkpoint_required"


def test_live_bridge_timeout_uses_env_override_and_maps_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_timeout: dict[str, float] = {}

    def _timeout_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        captured_timeout["value"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setenv("FL_MCP_BRIDGE_MODE", "live")
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_CMD", "bridge-runner")
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_TIMEOUT_SECONDS", "0.25")
    monkeypatch.setattr(subprocess, "run", _timeout_run)

    bridge = FLStudioBridge.from_environment()
    result = bridge.execute_change(
        DomainChange(
            domain="mixer",
            operation="set_volume",
            rollback_class="checkpointed",
            payload={},
        )
    )

    assert captured_timeout["value"] == 0.25
    assert result.success is False
    assert result.error_code == "bridge_timeout"


def test_live_bridge_timeout_invalid_env_uses_safe_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_timeout: dict[str, float] = {}

    def _success_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        captured_timeout["value"] = kwargs["timeout"]
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout='{"success": true}',
            stderr="",
        )

    monkeypatch.setenv("FL_MCP_BRIDGE_MODE", "live")
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_CMD", "bridge-runner")
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_TIMEOUT_SECONDS", "invalid")
    monkeypatch.setattr(subprocess, "run", _success_run)

    bridge = FLStudioBridge.from_environment()
    result = bridge.execute_change(
        DomainChange(
            domain="mixer",
            operation="set_volume",
            rollback_class="checkpointed",
            payload={},
        )
    )

    assert captured_timeout["value"] == DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS
    assert result.success is True


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "{}",
        "[]",
        "not-json",
        '{"success": "true"}',
    ],
)
def test_live_bridge_response_parsing_fails_closed_without_explicit_success_true(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
) -> None:
    def _run_with_output(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setenv("FL_MCP_BRIDGE_MODE", "live")
    monkeypatch.setenv("FL_MCP_FL_STUDIO_BRIDGE_CMD", "bridge-runner")
    monkeypatch.setattr(subprocess, "run", _run_with_output)

    bridge = FLStudioBridge.from_environment()
    result = bridge.execute_change(
        DomainChange(
            domain="mixer",
            operation="set_volume",
            rollback_class="checkpointed",
            payload={},
        )
    )

    assert result.success is False
    assert result.error_code == "invalid_response"
