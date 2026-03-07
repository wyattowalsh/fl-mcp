"""Apply engine with checkpoint metadata."""

from typing import Literal

from fl_mcp.schemas import TransactionEnvelope, TransactionResult


def apply_changes(envelope: TransactionEnvelope) -> TransactionResult:
    """Apply a planned transaction (skeleton)."""
    status: Literal["applied", "partially_applied"] = (
        "applied" if envelope.execution_policy == "all-or-nothing" else "partially_applied"
    )
    return TransactionResult(
        transaction_id=f"tx-{envelope.request_id}",
        status=status,
        checkpoint_id=f"ckpt-{envelope.request_id}",
        snapshot_before=envelope.target_snapshot_id,
        snapshot_after=f"snap-{envelope.request_id}",
        per_domain_results={change.domain: "applied" for change in envelope.changes},
        diff_summary={"change_count": len(envelope.changes)},
    )
