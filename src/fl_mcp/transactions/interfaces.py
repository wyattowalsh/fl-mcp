"""Planner/apply model interfaces with explicit mutation metadata."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Literal, TypedDict

from fl_mcp.schemas import DomainChange, RollbackClass


class ExecutionErrorCode(StrEnum):
    """Canonical error codes for apply-stage execution failures."""

    UNSUPPORTED_DOMAIN = "unsupported_domain"
    BRIDGE_PROCESS_ERROR = "bridge_process_error"
    BRIDGE_NONZERO_EXIT = "bridge_nonzero_exit"
    BRIDGE_TIMEOUT = "bridge_timeout"
    BRIDGE_DIR_INSECURE = "bridge_dir_insecure"
    LIVE_PROVIDER_UNAVAILABLE = "live_provider_unavailable"
    API_MISSING = "api_missing"
    UNSUPPORTED_HOST_BEHAVIOR = "unsupported_host_behavior"
    PATH_UNAVAILABLE = "path_unavailable"
    HOST_EXCEPTION = "host_exception"
    FL_HOST_TIMEOUT = "fl_host_timeout"
    SELECTED_CONTROLLER_BUSY = "selected_controller_busy"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    PROVIDER_STARTUP_FAILED = "provider_startup_failed"
    INVALID_REQUEST = "invalid_request"
    MOCK_FORCED_FAILURE = "mock_forced_failure"
    INVALID_RESPONSE = "invalid_response"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    UNKNOWN = "unknown"


class PlannerMutationIntent(TypedDict):
    """Planner-produced mutation intent."""

    domain: str
    operation: str
    rollback_class: RollbackClass


class ApplyMutationRequest(TypedDict):
    """Apply-stage mutation input containing execution details."""

    domain: str
    operation: str
    rollback_class: RollbackClass
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
    provider: str
    result: dict[str, object]


def domain_result_key(
    change: DomainChange,
    total_by_domain: Counter[str],
    seen: dict[str, int],
) -> str:
    """Generate a unique key for a domain result entry.

    When multiple changes target the same domain, keys are suffixed with
    a monotonically increasing index (e.g. ``mixer#2``).  When only one
    change targets a domain, the plain domain name is used.
    """
    seen[change.domain] += 1
    if total_by_domain[change.domain] == 1:
        return change.domain
    return f"{change.domain}#{seen[change.domain]}"
