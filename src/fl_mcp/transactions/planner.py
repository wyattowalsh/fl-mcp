"""Planner/compiler for typed transactions."""

from fl_mcp.schemas import TransactionEnvelope, TransactionResult


def plan_changes(envelope: TransactionEnvelope) -> TransactionResult:
    """Compile intent into a typed preview result."""
    return TransactionResult(
        transaction_id=f"plan-{envelope.request_id}",
        status="planned",
        snapshot_before=envelope.target_snapshot_id,
        per_domain_results={change.domain: "planned" for change in envelope.changes},
        diff_summary={"change_count": len(envelope.changes)},
        warnings=[] if envelope.changes else ["No changes requested"],
    )
