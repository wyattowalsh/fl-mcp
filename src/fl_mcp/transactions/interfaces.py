"""Planner/apply model interfaces with explicit mutation metadata."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol, TypedDict

from fl_mcp.schemas import RollbackClass, TransactionEnvelope


class ExecutionErrorCode(StrEnum):
    """Canonical error codes for apply-stage execution failures."""

    UNSUPPORTED_DOMAIN = "unsupported_domain"
    DOMAIN_UNSUPPORTED = "unsupported_domain"
    BRIDGE_PROCESS_ERROR = "bridge_process_error"
    LIVE_BRIDGE_UNAVAILABLE = "bridge_process_error"
    BRIDGE_NONZERO_EXIT = "bridge_nonzero_exit"
    BRIDGE_TIMEOUT = "bridge_timeout"
    LIVE_BRIDGE_TIMEOUT = "bridge_timeout"
    MOCK_FORCED_FAILURE = "mock_forced_failure"
    ADAPTER_FAILURE = "mock_forced_failure"
    INVALID_RESPONSE = "invalid_response"
    EXECUTION_FAILED = "execution_failed"
    UNKNOWN = "unknown"


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
    status: str
    message: str
    error_code: ExecutionErrorCode | None
    checkpoint_required: bool


class DomainExecutionReport(TypedDict):
    """Execution report returned by the apply stage."""

    domain: str
    operation: str
    success: bool
    rollback_class: RollbackClass
    status: Literal["previewed", "applied", "failed"]
    message: str
    error_code: ExecutionErrorCode | None
    execution_id: str | None


class PlannerModelInterface(Protocol):
    """Contract for planner models producing mutation intents."""

    def plan(self, envelope: TransactionEnvelope) -> list[PlannerMutationIntent]:
        """Generate ordered mutations for a transaction envelope."""


class ApplyModelInterface(Protocol):
    """Contract for apply models executing planned mutations."""

    def apply(self, mutation: ApplyMutationRequest) -> MutationResult:
        """Execute a mutation and return execution status."""
