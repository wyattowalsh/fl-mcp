"""Rollback class metadata mapped from mutation classification."""

from __future__ import annotations

from dataclasses import dataclass

from fl_mcp.schemas import RollbackClass


@dataclass(frozen=True, slots=True)
class RollbackPolicyMetadata:
    """Behavioral metadata for rollback orchestration."""

    classification: RollbackClass
    requires_checkpoint: bool
    supports_automatic_rollback: bool
    description: str


ROLLBACK_POLICY_BY_CLASSIFICATION: dict[RollbackClass, RollbackPolicyMetadata] = {
    "fully_transactional": RollbackPolicyMetadata(
        classification="fully_transactional",
        requires_checkpoint=False,
        supports_automatic_rollback=True,
        description="Change is atomic and can be rolled back automatically.",
    ),
    "checkpointed": RollbackPolicyMetadata(
        classification="checkpointed",
        requires_checkpoint=True,
        supports_automatic_rollback=True,
        description="Change requires explicit checkpoint before apply.",
    ),
    "best_effort": RollbackPolicyMetadata(
        classification="best_effort",
        requires_checkpoint=False,
        supports_automatic_rollback=False,
        description="Rollback may be partial; compensating action may be needed.",
    ),
    "unsafe_raw": RollbackPolicyMetadata(
        classification="unsafe_raw",
        requires_checkpoint=True,
        supports_automatic_rollback=False,
        description="Raw unsafe mutation with no guaranteed rollback semantics.",
    ),
}


def rollback_policy_for(classification: RollbackClass) -> RollbackPolicyMetadata:
    """Resolve rollback policy metadata for a classification."""
    return ROLLBACK_POLICY_BY_CLASSIFICATION[classification]
