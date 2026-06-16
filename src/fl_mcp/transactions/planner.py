"""Planner/compiler for typed transactions."""

import logging
from collections import Counter, defaultdict

from fl_mcp.middleware.safety import ensure_safe_mode
from fl_mcp.operations import validate_change
from fl_mcp.schemas import DomainChange, TransactionEnvelope, TransactionResult
from fl_mcp.transactions.interfaces import domain_result_key

logger = logging.getLogger(__name__)


def plan_changes(envelope: TransactionEnvelope) -> TransactionResult:
    """Compile intent into a typed preview result."""

    safety_mode = getattr(envelope, "safety_mode", "standard")
    ensure_safe_mode(safety_mode)
    if safety_mode != "standard":
        logger.info(
            "safety_mode='%s' accepted but not yet enforced (reserved) [%s]",
            safety_mode,
            getattr(envelope, "request_id", "unknown"),
        )

    total_by_domain: Counter[str] = Counter(change.domain for change in envelope.changes)
    seen: defaultdict[str, int] = defaultdict(int)
    per_domain_results: dict[str, str] = {}
    normalized_changes: list[DomainChange] = []

    for change in envelope.changes:
        _, normalized_change = validate_change(change)
        normalized_changes.append(normalized_change)
        key = domain_result_key(normalized_change, total_by_domain, seen)
        per_domain_results[key] = "planned"

    return TransactionResult(
        transaction_id=f"plan-{envelope.request_id}",
        status="planned",
        snapshot_before=envelope.target_snapshot_id,
        snapshot_after=envelope.target_snapshot_id,
        per_domain_results=per_domain_results,
        diff_summary={
            "mode": "preview",
            "change_count": len(normalized_changes),
            "validated_operations": [
                {
                    "domain": change.domain,
                    "operation": change.operation,
                    "payload": change.payload,
                }
                for change in normalized_changes
            ],
        },
        warnings=[] if envelope.changes else ["No changes requested"],
    )
