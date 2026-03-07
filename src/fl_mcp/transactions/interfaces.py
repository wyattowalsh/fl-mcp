"""Planner/apply model interfaces with explicit mutation metadata."""

from __future__ import annotations

from typing import Protocol, TypedDict

from fl_mcp.schemas import RollbackClass, TransactionEnvelope


class PlannerMutationIntent(TypedDict):
    """Planner-produced mutation intent."""

    domain: str
    operation: str
    rollback_class: RollbackClass
    target_node_id: str
    rationale: str


class ApplyMutationRequest(TypedDict):
    """Apply-stage mutation input containing execution details."""

    domain: str
    operation: str
    rollback_class: RollbackClass
    planned_mutation_id: str
    execution_provider: str


class MutationResult(TypedDict):
    """Execution status for an apply operation."""

    mutation_id: str
    success: bool
    rollback_class: RollbackClass


class PlannerModelInterface(Protocol):
    """Contract for planner models producing mutation intents."""

    def plan(self, envelope: TransactionEnvelope) -> list[PlannerMutationIntent]:
        """Generate ordered mutations for a transaction envelope."""


class ApplyModelInterface(Protocol):
    """Contract for apply models executing planned mutations."""

    def apply(self, mutation: ApplyMutationRequest) -> MutationResult:
        """Execute a mutation and return execution status."""
