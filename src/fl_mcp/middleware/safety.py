"""Safety gating for transaction safety_mode policy."""

from __future__ import annotations

from collections.abc import Sequence

from fl_mcp.exceptions import TransactionError
from fl_mcp.operations import OperationSpec, find_operation_for_change
from fl_mcp.schemas import DomainChange

_SUPPORTED_MODES = frozenset({"strict", "standard", "relaxed"})
_STRICTNESS_ORDER = {"strict": 0, "standard": 1, "relaxed": 2}


class SafetyModeError(TransactionError):
    """Raised when a request violates the configured safety_mode policy."""


def ensure_safe_mode(safety_mode: str) -> None:
    """Validate that ``safety_mode`` is a supported literal."""

    if safety_mode not in _SUPPORTED_MODES:
        raise ValueError(f"Unsupported safety mode: {safety_mode}")


def effective_safety_mode(envelope_mode: str, settings_mode: str) -> str:
    """Return the stricter of envelope and server safety modes (``strict`` wins)."""

    ensure_safe_mode(envelope_mode)
    if settings_mode not in {"strict", "standard"}:
        raise ValueError(f"Unsupported server safety mode: {settings_mode}")
    return (
        envelope_mode
        if _STRICTNESS_ORDER[envelope_mode] <= _STRICTNESS_ORDER[settings_mode]
        else settings_mode
    )


def _resolve_operation_spec(operation_id: str) -> OperationSpec | None:
    """Resolve compact ``operation_id`` (``domain.operation``) to an operation spec."""

    if "." not in operation_id:
        return None
    domain, operation = operation_id.split(".", 1)
    return find_operation_for_change(domain, operation)


def _operation_blocked_in_strict(operation_id: str) -> bool:
    spec = _resolve_operation_spec(operation_id)
    if spec is None:
        return True
    return spec.destructive


def _change_blocked_in_strict(change: DomainChange) -> bool:
    spec = find_operation_for_change(change.domain, change.operation)
    if spec is None:
        return True
    return spec.destructive


def enforce_operation_safety_mode(safety_mode: str, operation_id: str) -> None:
    """Enforce ``safety_mode`` for a single compact-surface operation id."""

    ensure_safe_mode(safety_mode)
    if safety_mode == "relaxed":
        raise SafetyModeError(
            "safety_mode='relaxed' is not supported. "
            "Use 'standard' for normal operation or 'strict' to block destructive changes."
        )
    if safety_mode != "strict":
        return

    if not _operation_blocked_in_strict(operation_id):
        return

    spec = _resolve_operation_spec(operation_id)
    if spec is None:
        raise SafetyModeError(
            f"safety_mode='strict' blocks unknown operation: {operation_id}. "
            "Use safety_mode='standard' or a known non-destructive operation."
        )
    raise SafetyModeError(
        f"safety_mode='strict' blocks destructive operation: {operation_id}. "
        "Use safety_mode='standard' or choose a non-destructive operation."
    )


def enforce_safety_mode(safety_mode: str, changes: Sequence[DomainChange]) -> None:
    """Validate and enforce ``safety_mode`` against transaction changes."""

    ensure_safe_mode(safety_mode)
    if safety_mode == "relaxed":
        raise SafetyModeError(
            "safety_mode='relaxed' is not supported. "
            "Use 'standard' for normal operation or 'strict' to block destructive changes."
        )
    if safety_mode != "strict":
        return

    blocked = [
        f"{change.domain}.{change.operation}"
        for change in changes
        if _change_blocked_in_strict(change)
    ]
    if not blocked:
        return

    joined = ", ".join(blocked)
    raise SafetyModeError(
        f"safety_mode='strict' blocks destructive or unknown operation(s): {joined}. "
        "Use safety_mode='standard' or remove blocked changes."
    )