"""Apply engine with rollback-aware execution metadata."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Literal

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE, BridgeExecutionResult
from fl_mcp.exceptions import ProviderError
from fl_mcp.config.settings import settings
from fl_mcp.middleware.safety import effective_safety_mode, enforce_safety_mode
from fl_mcp.operations import OperationPayloadValidationError, execute_change, validate_change
from fl_mcp.schemas import DomainChange, TransactionEnvelope, TransactionResult
from fl_mcp.transactions.interfaces import (
    DomainExecutionReport,
    ExecutionErrorCode,
    domain_result_key,
)
from fl_mcp.transactions.rollback import classify_execution_failure, rollback_policy_for

logger = logging.getLogger(__name__)


def _preview_result(envelope: TransactionEnvelope) -> TransactionResult:
    total_by_domain: Counter[str] = Counter(change.domain for change in envelope.changes)
    seen: defaultdict[str, int] = defaultdict(int)
    per_domain_results: dict[str, str] = {}

    for change in envelope.changes:
        key = domain_result_key(change, total_by_domain, seen)
        per_domain_results[key] = "planned"

    return TransactionResult(
        transaction_id=f"tx-{envelope.request_id}",
        status="planned",
        checkpoint_id=None,
        snapshot_before=envelope.target_snapshot_id,
        snapshot_after=envelope.target_snapshot_id,
        per_domain_results=per_domain_results,
        diff_summary={
            "mode": "preview",
            "change_count": len(envelope.changes),
            "applied_count": 0,
            "failed_count": 0,
        },
    )


def _normalize_error_code(error_code: str | ExecutionErrorCode | None) -> ExecutionErrorCode | None:
    if error_code is None:
        return None
    if isinstance(error_code, ExecutionErrorCode):
        return error_code
    try:
        return ExecutionErrorCode(error_code)
    except ValueError:
        return ExecutionErrorCode.UNKNOWN


def _validation_report(
    change: DomainChange,
    *,
    message: str,
    provider: str | None = None,
) -> DomainExecutionReport:
    return DomainExecutionReport(
        domain=change.domain,
        operation=change.operation,
        success=False,
        rollback_class=change.rollback_class,
        status="failed",
        message=message,
        error_code=ExecutionErrorCode.VALIDATION_FAILED,
        execution_id=None,
        provider=provider or change.provider or "unknown",
        result={},
    )


def _finalize_all_or_nothing_failure(
    *,
    execution_policy: Literal["all-or-nothing", "allow-partial"],
    overall_status: Literal["applied", "failed", "partially_applied"],
    keyed_changes: list[tuple[str, DomainChange]],
    execution_reports: list[DomainExecutionReport],
    per_domain_results: dict[str, str],
) -> tuple[int, int]:
    if execution_policy != "all-or-nothing" or overall_status != "failed":
        failed_count = sum(1 for report in execution_reports if not report["success"])
        applied_count = sum(1 for report in execution_reports if report["success"])
        return applied_count, failed_count

    for index, report in enumerate(execution_reports):
        if not report["success"]:
            continue

        key, change = keyed_changes[index]
        per_domain_results[key] = classify_execution_failure(change.rollback_class)
        report["success"] = False
        report["status"] = "failed"
        report["error_code"] = ExecutionErrorCode.EXECUTION_FAILED
        report["message"] = "Change was reverted due to all-or-nothing transaction failure."
        report["execution_id"] = None

    return 0, len(execution_reports)


def apply_changes(envelope: TransactionEnvelope) -> TransactionResult:
    """Apply or preview a planned transaction envelope."""

    envelope_mode = getattr(envelope, "safety_mode", "standard")
    if envelope_mode == "relaxed":
        enforce_safety_mode(envelope_mode, envelope.changes)
    safety_mode = effective_safety_mode(envelope_mode, settings.safety_mode)
    enforce_safety_mode(safety_mode, envelope.changes)

    logger.info(
        "Applying transaction %s with %d changes, policy=%s",
        envelope.request_id,
        len(envelope.changes),
        envelope.execution_policy,
    )

    if envelope.mode == "preview":
        return _preview_result(envelope)

    total_by_domain: Counter[str] = Counter(change.domain for change in envelope.changes)
    seen: defaultdict[str, int] = defaultdict(int)
    planned_changes: list[tuple[str, DomainChange, DomainChange | None, Exception | None]] = []
    keyed_changes: list[tuple[str, DomainChange]] = []
    per_domain_results: dict[str, str] = {}
    execution_reports: list[DomainExecutionReport] = []
    bridge_mode: str | None = None

    for change in envelope.changes:
        try:
            _, normalized_change = validate_change(change)
        except (OperationPayloadValidationError, ProviderError) as exc:
            key = domain_result_key(change, total_by_domain, seen)
            planned_changes.append((key, change, None, exc))
            continue
        key = domain_result_key(normalized_change, total_by_domain, seen)
        planned_changes.append((key, change, normalized_change, None))

    validation_failed = any(error is not None for _, _, _, error in planned_changes)
    if validation_failed and envelope.execution_policy == "all-or-nothing":
        for key, original_change, planned_normalized_change, validation_error in planned_changes:
            report_change = (
                planned_normalized_change
                if planned_normalized_change is not None
                else original_change
            )
            if validation_error is None:
                message = (
                    "Change was not executed because another change failed validation "
                    "under all-or-nothing transaction policy."
                )
            else:
                message = str(validation_error)
            per_domain_results[key] = classify_execution_failure(report_change.rollback_class)
            execution_reports.append(
                _validation_report(
                    report_change,
                    message=message,
                    provider=(
                        planned_normalized_change.provider
                        if planned_normalized_change is not None
                        else None
                    ),
                )
            )

        errors = [report["message"] for report in execution_reports]
        return TransactionResult(
            transaction_id=f"tx-{envelope.request_id}",
            status="failed",
            checkpoint_id=None,
            snapshot_before=envelope.target_snapshot_id,
            snapshot_after=envelope.target_snapshot_id,
            per_domain_results=per_domain_results,
            diff_summary={
                "mode": "apply",
                "bridge_mode": "unknown",
                "change_count": len(envelope.changes),
                "applied_count": 0,
                "failed_count": len(execution_reports),
                "reports": execution_reports,
            },
            warnings=[],
            errors=errors,
            rollback_capability=(
                "partial"
                if any(
                    not rollback_policy_for(change.rollback_class).supports_automatic_rollback
                    for change in envelope.changes
                )
                else "available"
            ),
        )

    for key, original_change, planned_normalized_change, validation_error in planned_changes:
        if validation_error is not None:
            per_domain_results[key] = classify_execution_failure(original_change.rollback_class)
            execution_reports.append(
                _validation_report(original_change, message=str(validation_error))
            )
            continue
        if planned_normalized_change is None:  # pragma: no cover - defensive guard
            continue
        keyed_changes.append((key, planned_normalized_change))

    for key, change in keyed_changes:
        try:
            bridge_result = execute_change(change)
        except Exception as exc:
            logger.warning(
                "Domain %s op %s raised unexpectedly [%s]: %s",
                change.domain,
                change.operation,
                envelope.request_id,
                exc,
                exc_info=True,
            )
            bridge_result = BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                error_code="unexpected_error",
                message=str(exc),
                execution_id=None,
                bridge_mode=DEFAULT_BRIDGE.mode,
                provider="unknown",
                result={},
            )
        bridge_mode = bridge_result.bridge_mode

        if bridge_result.success:
            result_status = "applied"
            error_code = None
        else:
            result_status = classify_execution_failure(change.rollback_class)
            error_code = _normalize_error_code(bridge_result.error_code)
            logger.warning(
                "Domain %s op %s failed [%s] provider=%s rollback=%s: %s",
                change.domain,
                change.operation,
                envelope.request_id,
                change.provider,
                change.rollback_class,
                error_code,
            )

        per_domain_results[key] = result_status
        execution_reports.append(
            DomainExecutionReport(
                domain=change.domain,
                operation=change.operation,
                success=bridge_result.success,
                rollback_class=change.rollback_class,
                status="applied" if bridge_result.success else "failed",
                message=bridge_result.message,
                error_code=error_code,
                execution_id=bridge_result.execution_id,
                provider=bridge_result.provider,
                result=bridge_result.result,
            )
        )

    applied_count = sum(1 for report in execution_reports if report["success"])
    failed_count = len(execution_reports) - applied_count

    if failed_count == 0:
        overall_status: Literal["applied", "failed", "partially_applied"] = "applied"
    elif applied_count and envelope.execution_policy == "allow-partial":
        overall_status = "partially_applied"
    else:
        overall_status = "failed"

    applied_count, failed_count = _finalize_all_or_nothing_failure(
        execution_policy=envelope.execution_policy,
        overall_status=overall_status,
        keyed_changes=keyed_changes,
        execution_reports=execution_reports,
        per_domain_results=per_domain_results,
    )

    errors = [report["message"] for report in execution_reports if not report["success"]]
    warnings: list[str] = []
    if failed_count and envelope.execution_policy == "allow-partial":
        warnings.append("One or more changes failed under allow-partial execution policy.")

    snapshot_after = (
        f"snap-{envelope.request_id}"
        if overall_status in {"applied", "partially_applied"}
        else envelope.target_snapshot_id
    )

    logger.info(
        "Transaction %s completed: status=%s",
        envelope.request_id,
        overall_status,
    )

    return TransactionResult(
        transaction_id=f"tx-{envelope.request_id}",
        status=overall_status,
        checkpoint_id=(
            f"ckpt-{envelope.request_id}"
            if applied_count and overall_status in {"applied", "partially_applied"}
            else None
        ),
        snapshot_before=envelope.target_snapshot_id,
        snapshot_after=snapshot_after,
        per_domain_results=per_domain_results,
        diff_summary={
            "mode": "apply",
            "bridge_mode": bridge_mode or "unknown",
            "change_count": len(envelope.changes),
            "applied_count": applied_count,
            "failed_count": failed_count,
            "reports": execution_reports,
        },
        warnings=warnings,
        errors=errors,
        rollback_capability=(
            "partial"
            if any(
                not rollback_policy_for(change.rollback_class).supports_automatic_rollback
                for change in envelope.changes
            )
            else "available"
        ),
    )
