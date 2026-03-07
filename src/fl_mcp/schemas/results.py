"""Result schemas for mutation and transaction execution."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from .transactions import RollbackClassification


class MutationResult(BaseModel):
    """Execution result for a single mutation."""

    model_config = ConfigDict(extra="forbid")

    mutation_id: str = Field(..., description="Identifier of executed mutation.")
    success: bool = Field(..., description="Whether mutation executed successfully.")
    rollback_classification: RollbackClassification = Field(
        ..., description="Rollback/checkpoint classification from the mutation model."
    )
    message: str | None = Field(None, description="Optional human-readable execution status.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata.")


class TransactionResult(BaseModel):
    """Aggregate result for a transaction execution."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Identifier of the transaction.")
    committed: bool = Field(..., description="Whether all required mutations committed.")
    rolled_back: bool = Field(..., description="Whether rollback was attempted or completed.")
    mutation_results: list[MutationResult] = Field(
        default_factory=list,
        description="Per-mutation execution outcomes.",
    )
