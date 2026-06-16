from __future__ import annotations

import subprocess
from typing import cast

import pytest

from fl_mcp.bridge.fl_studio import (
    DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS,
    BridgeExecutionResult,
    FLStudioBridge,
)
from fl_mcp.operations import validate_change
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


def test_apply_changes_all_or_nothing_validation_failure_prevents_bridge_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_execute(change: DomainChange) -> object:
        raise AssertionError(f"bridge should not execute {change.domain}.{change.operation}")

    monkeypatch.setattr("fl_mcp.transactions.apply.execute_change", _unexpected_execute)
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-validation-1",
            "mode": "apply",
            "execution_policy": "all-or-nothing",
            "changes": [
                {
                    "domain": "transport",
                    "operation": "set_tempo",
                    "rollback_class": "checkpointed",
                    "payload": {},
                },
                {
                    "domain": "transport",
                    "operation": "get_state",
                    "rollback_class": "best_effort",
                    "payload": {},
                },
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert result.status == "failed"
    assert result.diff_summary["applied_count"] == 0
    assert result.diff_summary["failed_count"] == 2
    assert isinstance(reports, list)
    assert [report["success"] for report in reports] == [False, False]
    assert {report["error_code"] for report in reports} == {"validation_failed"}
    assert "bpm" in result.errors[0]


def test_apply_changes_allow_partial_reports_validation_failure_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _execute(change: DomainChange) -> BridgeExecutionResult:
        return BridgeExecutionResult(
            domain=change.domain,
            operation=change.operation,
            success=True,
            message="ok",
            error_code=None,
            execution_id="valid-change",
            bridge_mode="mock",
            provider=change.provider or "mock",
            result={"ok": True},
        )

    monkeypatch.setattr("fl_mcp.transactions.apply.execute_change", _execute)
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-validation-2",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "transport",
                    "operation": "set_tempo",
                    "rollback_class": "checkpointed",
                    "payload": {},
                },
                {
                    "domain": "transport",
                    "operation": "get_state",
                    "rollback_class": "best_effort",
                    "payload": {},
                },
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert result.status == "partially_applied"
    assert result.diff_summary["applied_count"] == 1
    assert result.diff_summary["failed_count"] == 1
    assert isinstance(reports, list)
    assert reports[0]["error_code"] == "validation_failed"
    assert reports[1]["success"] is True
    assert reports[1]["execution_id"] == "valid-change"


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


def test_apply_changes_normalizes_explicit_surface_aliases() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-5",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "patterns",
                    "operation": "select",
                    "rollback_class": "unsafe_raw",
                    "payload": {"pattern_index": 1},
                }
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert result.status == "applied"
    assert isinstance(reports, list)
    assert reports[0]["operation"] == "select_pattern"
    assert reports[0]["provider"] == "mock"
    assert result.per_domain_results["patterns"] == "applied"


def test_apply_changes_canonicalizes_provider_aliases_and_fails_closed_in_mock_mode() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-6",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "transport",
                    "operation": "set_tempo",
                    "rollback_class": "checkpointed",
                    "provider": "flapi",
                    "payload": {"bpm": 140},
                }
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert result.status == "failed"
    assert isinstance(reports, list)
    assert reports[0]["provider"] == "flapi-live"
    assert reports[0]["error_code"] == "live_provider_unavailable"


def test_validate_change_canonicalizes_provider_aliases_before_execution() -> None:
    spec, normalized = validate_change(
        DomainChange(
            domain="transport",
            operation="set_tempo",
            rollback_class="checkpointed",
            provider="flapi",
            payload={"bpm": 140},
        )
    )

    assert spec is not None
    assert normalized.provider == "flapi-live"
    assert normalized.operation == "set_tempo"
    assert normalized.payload == {"bpm": 140}


def test_apply_changes_uses_mock_default_providers_outside_live_mode() -> None:
    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-7",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "connection",
                    "operation": "connect",
                    "rollback_class": "best_effort",
                    "payload": {},
                },
                {
                    "domain": "patterns",
                    "operation": "create",
                    "rollback_class": "checkpointed",
                    "payload": {"name": "Bridge"},
                },
                {
                    "domain": "channels",
                    "operation": "set_step_sequence",
                    "rollback_class": "best_effort",
                    "payload": {"channel_index": 0, "steps": [0, 4, 8, 12]},
                },
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert isinstance(reports, list)
    assert [report["provider"] for report in reports] == ["mock", "mock", "mock"]


def test_apply_changes_preserves_live_provider_error_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **_: object) -> object:
            return type(
                "ProviderResult",
                (),
                {
                    "success": False,
                    "provider": provider,
                    "bridge_mode": "live",
                    "execution_id": "apply-live-failure",
                    "message": "FL host API callable not found for automation.create_clip.",
                    "error_code": "api_missing",
                    "result": {"operation_id": "automation.create_clip"},
                },
            )()

    monkeypatch.setattr(
        "fl_mcp.providers.runtime.get_provider_registry",
        lambda load_entry_points=False: Registry(),
    )

    envelope = TransactionEnvelope.model_validate(
        {
            "request_id": "tx-apply-live-error",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "automation",
                    "operation": "create_clip",
                    "rollback_class": "checkpointed",
                    "provider": "flapi-live",
                    "payload": {"name": "Filter Sweep"},
                }
            ],
        }
    )

    result = apply_changes(envelope)
    reports = result.diff_summary["reports"]

    assert result.status == "failed"
    assert isinstance(reports, list)
    assert reports[0]["provider"] == "flapi-live"
    assert reports[0]["error_code"] == "api_missing"


def test_live_bridge_timeout_uses_env_override_and_maps_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_timeout: dict[str, float] = {}

    def _timeout_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], args[0])
        timeout = cast(float, kwargs["timeout"])
        captured_timeout["value"] = timeout
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

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

    def _success_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], args[0])
        timeout = cast(float, kwargs["timeout"])
        captured_timeout["value"] = timeout
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"success": true, "message": "ok"}',
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
    def _run_with_output(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], args[0])
        return subprocess.CompletedProcess(
            args=command,
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
