"""Apply engine with rollback-aware execution metadata."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Literal

from fl_mcp.bridge.fl_studio import FLStudioBridge
from fl_mcp.schemas import DomainChange, TransactionEnvelope, TransactionResult
from fl_mcp.transactions.interfaces import DomainExecutionReport, ExecutionErrorCode
from fl_mcp.transactions.rollback import classify_execution_failure, rollback_policy_for


def _domain_result_key(
    change: DomainChange,
    total_by_domain: Counter[str],
    seen: dict[str, int],
) -> str:
    seen[change.domain] += 1
    if total_by_domain[change.domain] == 1:
        return change.domain
    return f"{change.domain}#{seen[change.domain]}"


def _preview_result(envelope: TransactionEnvelope) -> TransactionResult:
    total_by_domain: Counter[str] = Counter(change.domain for change in envelope.changes)
    seen: defaultdict[str, int] = defaultdict(int)
    per_domain_results: dict[str, str] = {}

    for change in envelope.changes:
        key = _domain_result_key(change, total_by_domain, seen)
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

    if envelope.mode == "preview":
        return _preview_result(envelope)

    bridge = FLStudioBridge.from_environment()
    total_by_domain: Counter[str] = Counter(change.domain for change in envelope.changes)
    seen: defaultdict[str, int] = defaultdict(int)
    keyed_changes: list[tuple[str, DomainChange]] = []
    per_domain_results: dict[str, str] = {}
    execution_reports: list[DomainExecutionReport] = []

    for change in envelope.changes:
        key = _domain_result_key(change, total_by_domain, seen)
        keyed_changes.append((key, change))

    for key, change in keyed_changes:
        bridge_result = bridge.execute_change(change)

        if bridge_result.success:
            result_status = "applied"
            error_code = None
        else:
            result_status = classify_execution_failure(change.rollback_class)
            error_code = _normalize_error_code(bridge_result.error_code)

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
            "bridge_mode": bridge.mode,
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
