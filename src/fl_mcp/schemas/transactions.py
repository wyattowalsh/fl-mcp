"""Schema models for transaction envelopes and mutation metadata."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class RollbackClassification(str, Enum):
    """Rollback semantics for mutation models."""

    fully_transactional = "fully_transactional"
    checkpointed = "checkpointed"
    best_effort = "best_effort"
    unsafe_raw = "unsafe_raw"


class MutationModel(BaseModel):
    """Base mutation type requiring rollback/checkpoint classification."""

    model_config = ConfigDict(extra="forbid")

    mutation_type: str = Field(..., description="Canonical mutation type identifier.")
    rollback_classification: RollbackClassification = Field(
        ..., description="Rollback/checkpoint classification for this mutation."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional model-specific metadata used during planning/apply.",
    )


class TransactionEnvelope(BaseModel):
    """Envelope wrapping one or more mutations into an atomic transaction intent."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Globally unique transaction identifier.")
    project_id: str = Field(..., description="Project identifier for graph resolution.")
    initiated_by: str = Field(..., description="Actor principal or service account ID.")
    mutations: list[MutationModel] = Field(
        default_factory=list,
        description="Ordered list of mutation intents to apply.",
    )
    dry_run: bool = Field(False, description="Evaluate transaction without persisting mutations.")
