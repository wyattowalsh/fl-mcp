"""Compatibility facade backed by the canonical explicit FL Studio tool catalog."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ValidationError

from fl_mcp.bridge.fl_studio import BridgeExecutionResult, BridgeMode
from fl_mcp.schemas import DomainChange, RollbackClass

if TYPE_CHECKING:
    from fl_mcp.tools.fl_surface import FLToolSpec

logger = logging.getLogger(__name__)

_CHANGE_ALIASES: dict[tuple[str, str], tuple[str, str]] = {
    ("channels", "list"): ("channels", "list_channels"),
    ("channels", "get_info"): ("channels", "get_channel"),
    ("mixer", "get_track_info"): ("mixer", "get_track"),
    ("patterns", "list"): ("patterns", "list_patterns"),
    ("patterns", "select"): ("patterns", "select_pattern"),
    ("patterns", "create"): ("patterns", "create_pattern"),
    ("patterns", "rename"): ("patterns", "rename_pattern"),
    ("playlist", "get_track_info"): ("playlist", "get_track"),
    ("plugins", "list_params"): ("plugins", "get_parameters"),
    ("ui", "get_visible"): ("ui", "get_visibility"),
}


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """Compatibility view of one operation in the canonical FL tool catalog."""

    name: str
    domain: str
    operation: str
    description: str
    request_model: type[BaseModel]
    rollback_class: RollbackClass | None
    provider: str
    tags: tuple[str, ...]
    read_only: bool
    destructive: bool
    idempotent: bool
    task: bool
    timeout_seconds: float | None


class OperationPayloadValidationError(ValueError):
    """Raised when a catalog-backed operation payload fails schema validation."""

    def __init__(
        self,
        *,
        domain: str,
        operation: str,
        request_model: type[BaseModel],
        validation_error: ValidationError,
    ) -> None:
        self.domain = domain
        self.operation = operation
        self.request_model = request_model
        self.validation_error = validation_error
        super().__init__(
            f"Payload for {domain}.{operation} failed "
            f"{request_model.__name__} validation: {validation_error}"
        )


@functools.cache
def _tool_modules() -> tuple[
    tuple[FLToolSpec, ...],
    dict[str, Callable[..., dict[str, object]]],
    dict[tuple[str, str], FLToolSpec],
    dict[str, dict[str, object]],
]:
    from fl_mcp.tools.fl_surface import (
        FL_TOOL_BY_CHANGE,
        FL_TOOL_HANDLERS,
        FL_TOOL_SPECS,
        PROVIDER_MATRIX,
    )

    return FL_TOOL_SPECS, FL_TOOL_HANDLERS, FL_TOOL_BY_CHANGE, PROVIDER_MATRIX


def _provider_for_operation(domain: str, operation: str) -> str:
    from fl_mcp.bridge.fl_studio import default_provider_for_operation

    return default_provider_for_operation(domain, operation)


def _normalize_provider(provider: str | None, default_provider: str) -> str:
    if provider is None or provider == "auto":
        return default_provider

    from fl_mcp.providers.runtime import get_provider_registry

    registry = get_provider_registry(load_entry_points=False)
    resolved = registry.resolve_name(provider)
    registry.get(resolved)
    return resolved


def _normalize_payload(
    request_model: type[BaseModel],
    payload: dict[str, object],
    *,
    domain: str,
    operation: str,
) -> dict[str, object]:
    try:
        validated = request_model.model_validate(payload)
    except ValidationError as exc:
        logger.debug("Payload normalization failed for %s: %s", request_model.__name__, exc)
        raise OperationPayloadValidationError(
            domain=domain,
            operation=operation,
            request_model=request_model,
            validation_error=exc,
        ) from exc

    normalized = validated.model_dump(exclude_none=True)
    normalized.pop("provider", None)
    normalized.pop("session_label", None)
    return normalized


def _resolve_change_key(domain: str, operation: str) -> tuple[str, str]:
    return _CHANGE_ALIASES.get((domain, operation), (domain, operation))


def _as_operation_spec(spec: FLToolSpec) -> OperationSpec:
    annotations = dict(spec.annotations)
    return OperationSpec(
        name=spec.name,
        domain=spec.domain,
        operation=spec.operation,
        description=spec.description,
        request_model=spec.request_model,
        rollback_class=spec.rollback_class,
        provider=_provider_for_operation(spec.domain, spec.operation),
        tags=spec.tags,
        read_only=bool(annotations.get("readOnlyHint")),
        destructive=bool(annotations.get("destructiveHint")),
        idempotent=bool(annotations.get("idempotentHint")),
        task=spec.task,
        timeout_seconds=spec.timeout,
    )


def list_operation_specs() -> tuple[OperationSpec, ...]:
    """Return all registered FL operation specs from the canonical tool catalog."""
    specs, _, _, _ = _tool_modules()
    return tuple(_as_operation_spec(spec) for spec in specs)


def get_operation_spec(name: str) -> OperationSpec:
    """Look up a single operation spec by tool name.

    Args:
        name: Canonical tool name (e.g. ``"fl_mixer_get_track"``).

    Raises:
        KeyError: If no tool with the given name exists.
    """
    from fl_mcp.tools.fl_surface import FL_TOOL_BY_NAME

    spec = FL_TOOL_BY_NAME.get(name)
    if spec is None:
        msg = f"Unknown FL operation tool '{name}'."
        raise KeyError(msg)
    return _as_operation_spec(spec)


def find_operation_for_change(domain: str, operation: str) -> OperationSpec | None:
    """Find the operation spec matching a domain/operation change key.

    Args:
        domain: FL Studio domain (e.g. ``"mixer"``).
        operation: Operation verb (e.g. ``"get_track"``).

    Returns:
        The matching spec, or ``None`` if no canonical tool covers this change.
    """
    _, _, specs_by_change, _ = _tool_modules()
    resolved_domain, resolved_operation = _resolve_change_key(domain, operation)
    spec = specs_by_change.get((resolved_domain, resolved_operation))
    if spec is None:
        return None
    return _as_operation_spec(spec)


def runtime_capability_payload() -> dict[str, object]:
    """Return the full runtime capability catalog payload."""
    from fl_mcp.tools.fl_surface import capability_catalog

    return capability_catalog()


def build_operation_tool_handlers() -> dict[str, Callable[..., dict[str, object]]]:
    """Build a mapping of tool name to handler callable for all FL operations."""
    _, handlers, _, _ = _tool_modules()
    return dict(handlers)


def execute_operation_tool(
    name: str,
    request: BaseModel | dict[str, object] | None = None,
) -> dict[str, object]:
    """Execute an FL operation tool by name.

    Args:
        name: Canonical tool name.
        request: Optional request payload as a model instance or raw dict.

    Returns:
        Result dict from the tool handler.
    """
    spec = get_operation_spec(name)
    _, handlers, _, _ = _tool_modules()
    handler = handlers[name]
    request_model = spec.request_model
    if request is None:
        validated = request_model()
    elif isinstance(request, BaseModel):
        validated = request_model.model_validate(request.model_dump(exclude_none=True))
    else:
        validated = request_model.model_validate(request)
    return dict(handler(validated))


def validate_change(change: DomainChange) -> tuple[OperationSpec | None, DomainChange]:
    """Resolve a change against the canonical FL surface without breaking raw fallbacks."""

    spec = find_operation_for_change(change.domain, change.operation)
    if spec is None:
        return None, change

    resolved_domain, resolved_operation = _resolve_change_key(change.domain, change.operation)
    normalized_change = change.model_copy(
        update={
            "domain": resolved_domain,
            "operation": resolved_operation,
            "rollback_class": spec.rollback_class or change.rollback_class,
            "provider": _normalize_provider(change.provider, spec.provider),
            "payload": _normalize_payload(
                spec.request_model,
                change.payload,
                domain=resolved_domain,
                operation=resolved_operation,
            ),
        }
    )
    return spec, normalized_change


def execute_change(change: DomainChange) -> BridgeExecutionResult:
    """Execute a change through the shared bridge path used by explicit tools."""

    from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE
    from fl_mcp.providers.runtime import get_provider_registry

    spec, normalized_change = validate_change(change)
    if spec is not None and normalized_change.provider not in {None, "auto", "mock"}:
        provider_result = get_provider_registry(load_entry_points=False).execute(
            str(normalized_change.provider),
            domain=normalized_change.domain,
            operation=normalized_change.operation,
            payload=normalized_change.payload,
        )
        raw_bridge_mode = provider_result.bridge_mode or DEFAULT_BRIDGE.mode
        bridge_mode = (
            raw_bridge_mode if raw_bridge_mode in {"mock", "live"} else DEFAULT_BRIDGE.mode
        )
        return BridgeExecutionResult(
            domain=normalized_change.domain,
            operation=normalized_change.operation,
            success=provider_result.success,
            message=provider_result.message,
            error_code=provider_result.error_code,
            execution_id=provider_result.execution_id,
            bridge_mode=cast(BridgeMode, bridge_mode),
            provider=provider_result.provider,
            result=provider_result.result,
        )
    return DEFAULT_BRIDGE.execute_change(normalized_change)


__all__ = [
    "OperationSpec",
    "build_operation_tool_handlers",
    "execute_change",
    "execute_operation_tool",
    "find_operation_for_change",
    "get_operation_spec",
    "list_operation_specs",
    "runtime_capability_payload",
    "validate_change",
]
