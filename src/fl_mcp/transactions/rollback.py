"""Rollback class metadata mapped from mutation classification."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from fl_mcp.schemas.transactions import RollbackClassification


class RollbackPolicyMetadata(BaseModel):
    """Behavioral metadata for rollback orchestration."""

    model_config = ConfigDict(extra="forbid")

    classification: RollbackClassification = Field(...)
    requires_checkpoint: bool = Field(...)
    supports_automatic_rollback: bool = Field(...)
    description: str = Field(...)


ROLLBACK_POLICY_BY_CLASSIFICATION: dict[RollbackClassification, RollbackPolicyMetadata] = {
    RollbackClassification.fully_transactional: RollbackPolicyMetadata(
        classification=RollbackClassification.fully_transactional,
        requires_checkpoint=False,
        supports_automatic_rollback=True,
        description="Change is atomic and can be rolled back automatically.",
    ),
    RollbackClassification.checkpointed: RollbackPolicyMetadata(
        classification=RollbackClassification.checkpointed,
        requires_checkpoint=True,
        supports_automatic_rollback=True,
        description="Change requires explicit checkpoint before apply.",
    ),
    RollbackClassification.best_effort: RollbackPolicyMetadata(
        classification=RollbackClassification.best_effort,
        requires_checkpoint=False,
        supports_automatic_rollback=False,
        description="Rollback may be partial; compensating action may be needed.",
    ),
    RollbackClassification.unsafe_raw: RollbackPolicyMetadata(
        classification=RollbackClassification.unsafe_raw,
        requires_checkpoint=True,
        supports_automatic_rollback=False,
        description="Raw unsafe mutation with no guaranteed rollback semantics.",
    ),
}


def rollback_policy_for(classification: RollbackClassification) -> RollbackPolicyMetadata:
    """Resolve rollback policy metadata for a classification."""

    return ROLLBACK_POLICY_BY_CLASSIFICATION[classification]
