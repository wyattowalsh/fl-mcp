"""Planner/apply model interfaces with explicit mutation metadata."""

from __future__ import annotations

from typing import Protocol

from pydantic import ConfigDict, Field

from fl_mcp.schemas.results import MutationResult
from fl_mcp.schemas.transactions import MutationModel, TransactionEnvelope


class PlannerMutationIntent(MutationModel):
    """Planner-produced mutation intent."""

    model_config = ConfigDict(extra="forbid")

    target_node_id: str = Field(..., description="Graph node that mutation targets.")
    rationale: str = Field(..., description="Planner explanation for the mutation.")


class ApplyMutationRequest(MutationModel):
    """Apply-stage mutation input containing execution details."""

    model_config = ConfigDict(extra="forbid")

    planned_mutation_id: str = Field(..., description="Planner mutation identifier.")
    execution_provider: str = Field(..., description="Provider implementing this mutation.")


class PlannerModelInterface(Protocol):
    """Contract for planner models producing mutation intents."""

    def plan(self, envelope: TransactionEnvelope) -> list[PlannerMutationIntent]:
        """Generate ordered mutations for a transaction envelope."""


class ApplyModelInterface(Protocol):
    """Contract for apply models executing planned mutations."""

    def apply(self, mutation: ApplyMutationRequest) -> MutationResult:
        """Execute a mutation and return execution status."""
