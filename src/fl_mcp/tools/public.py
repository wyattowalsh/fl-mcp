"""Public MCP tool handlers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import cast

from pydantic import ValidationError

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.middleware.safety import SafetyModeError
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.runtime.state import get_runtime_state
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.schemas.fl_tools import AudioAnalyzeRequest, FLToolRequest, RenderExportRequest
from fl_mcp.schemas.runtime_surface import (
    InspectRuntimeResponse,
    ManageProvidersResponse,
    RuntimeCapabilityCounts,
    RuntimePromptDescriptorModel,
    RuntimeResourceDescriptorModel,
    RuntimeToolDescriptorModel,
)
from fl_mcp.tools.fl_surface import FL_TOOL_HANDLERS, PROVIDER_MATRIX, capability_catalog
from fl_mcp.transactions.apply import apply_changes as apply_engine
from fl_mcp.transactions.planner import plan_changes as plan_engine

logger = logging.getLogger(__name__)

_DISABLED_PUBLIC_PROVIDER_ACTION_ERRORS: dict[str, str] = {
    "discover": "action=discover is disabled on the public MCP surface",
    "load_module": "action=load_module is disabled on the public MCP surface",
}
_PUBLIC_PROVIDER_ACTIONS = frozenset({"list", "startup", "shutdown"})

RuntimeToolDescriptor = RuntimeToolDescriptorModel
RuntimeResourceDescriptor = RuntimeResourceDescriptorModel
RuntimePromptDescriptor = RuntimePromptDescriptorModel


def _provider_statuses() -> list[dict[str, object]]:
    provider_registry = get_provider_registry(load_entry_points=False)
    return [dict(status) for status in provider_registry.statuses()]


def _normalize_query_project_inputs(
    domain_or_graph: str | ProjectGraph | dict[str, object],
    graph_or_domain: ProjectGraph | dict[str, object] | str | None,
) -> tuple[str, ProjectGraph | dict[str, object] | None]:
    if isinstance(domain_or_graph, str):
        if isinstance(graph_or_domain, str):
            msg = "query_project graph override must be a ProjectGraph or dict."
            raise TypeError(msg)
        return domain_or_graph, graph_or_domain
    if isinstance(graph_or_domain, str):
        return graph_or_domain, domain_or_graph
    msg = "query_project expects (domain[, graph]) or legacy (graph, domain)."
    raise TypeError(msg)


def query_project(
    domain: str | ProjectGraph | dict[str, object],
    graph: ProjectGraph | dict[str, object] | str | None = None,
) -> dict[str, object]:
    """Query the canonical project graph for a specific domain projection.

    Args:
        domain: Domain name to project, or a legacy first positional graph override.
        graph: Optional graph override when ``domain`` is a string, or the legacy
            domain name when ``domain`` is a graph-like input.

    Returns:
        Domain projection dict, or an error dict on validation failure.
    """
    try:
        active_domain, graph_override = _normalize_query_project_inputs(domain, graph)
        if graph_override is None:
            active_graph = get_runtime_state().snapshot_graph()
        else:
            active_graph = ProjectGraph.model_validate(graph_override)
        return active_graph.to_projection(active_domain)
    except (ValidationError, TypeError) as exc:
        logger.warning("Validation error in query_project: %s", exc, exc_info=True)
        return {"status": "error", "tool": "query_project", "error": str(exc)}


def plan_changes(envelope: TransactionEnvelope) -> dict[str, object]:
    """Validate and preview a transaction envelope without applying changes.

    Args:
        envelope: The transaction envelope to plan.

    Returns:
        Serialized TransactionResult dict with status "planned", or an error dict.
    """
    try:
        return plan_engine(envelope).model_dump()
    except (ValidationError, TypeError, AttributeError, SafetyModeError) as exc:
        logger.warning("Validation error in plan_changes: %s", exc, exc_info=True)
        return {"status": "error", "tool": "plan_changes", "error": str(exc)}


def apply_changes(envelope: TransactionEnvelope) -> dict[str, object]:
    """Execute a transaction envelope and return the apply result.

    Args:
        envelope: The transaction envelope to apply.

    Returns:
        Serialized TransactionResult dict, or an error dict on failure.
    """
    try:
        return apply_engine(envelope).model_dump()
    except (ValidationError, TypeError, AttributeError, SafetyModeError) as exc:
        logger.warning("Validation error in apply_changes: %s", exc, exc_info=True)
        return {"status": "error", "tool": "apply_changes", "error": str(exc)}


def _dispatch_task_tool(
    request_model: type[FLToolRequest],
    request: object,
    handler_key: str,
    tool_name: str,
    id_field: str,
) -> dict[str, object]:
    try:
        payload = request_model.model_validate(request or {})
        result = FL_TOOL_HANDLERS[handler_key](payload)
        task = result.get("task")
        if isinstance(task, dict):
            task_payload = cast(dict[str, object], task)
            task_id = task_payload.get("id")
            if not isinstance(task_id, str):
                return result
            result["tool"] = tool_name
            result[id_field] = task_id
            result["task_status"] = task_payload.get("state", "queued")
            result["execution_id"] = task_id
        return result
    except (ValidationError, TypeError) as exc:
        logger.warning("Validation error in %s: %s", tool_name, exc, exc_info=True)
        return {"status": "error", "tool": tool_name, "error": str(exc)}


def render_project(request: RenderExportRequest | None = None) -> dict[str, object]:
    """Start an FL Studio render/export task.

    Args:
        request: Export parameters; defaults are used when None.

    Returns:
        Task result dict with job_id and execution status.
    """
    return _dispatch_task_tool(
        RenderExportRequest, request, "render_export", "render_project", "job_id"
    )


def analyze_audio(request: AudioAnalyzeRequest | None = None) -> dict[str, object]:
    """Start an audio analysis task.

    Args:
        request: Analysis parameters; defaults are used when None.

    Returns:
        Task result dict with analysis_id and execution status.
    """
    return _dispatch_task_tool(
        AudioAnalyzeRequest, request, "audio_analyze", "analyze_audio", "analysis_id"
    )


def inspect_runtime(
    *,
    tools: Sequence[RuntimeToolDescriptor | dict[str, object]] | None = None,
    resources: Sequence[RuntimeResourceDescriptor | dict[str, object]] | None = None,
    prompts: Sequence[RuntimePromptDescriptor | dict[str, object]] | None = None,
    runtime_health_data: dict[str, str] | None = None,
    auth_required: bool = False,
    fastmcp_runtime: bool | None = None,
    transport: str = "unknown",
) -> dict[str, object]:
    """Assemble a runtime inspection snapshot.

    Returns:
        Serialized InspectRuntimeResponse dict.
    """
    provider_registry = get_provider_registry(load_entry_points=False)

    runtime_tools = sorted(
        (RuntimeToolDescriptorModel.model_validate(item) for item in (tools or [])),
        key=lambda item: item.name,
    )
    runtime_resources = sorted(
        (RuntimeResourceDescriptorModel.model_validate(item) for item in (resources or [])),
        key=lambda item: item.uri,
    )
    runtime_prompts = sorted(
        (RuntimePromptDescriptorModel.model_validate(item) for item in (prompts or [])),
        key=lambda item: item.name,
    )

    response = InspectRuntimeResponse(
        transport=transport,
        fastmcp_runtime=fastmcp_runtime,
        auth_required=auth_required,
        runtime_health=runtime_health_data or {},
        capabilities=RuntimeCapabilityCounts(
            tool_count=len(runtime_tools),
            resource_count=len(runtime_resources),
            prompt_count=len(runtime_prompts),
            fl_tool_count=len(FL_TOOL_HANDLERS),
        ),
        tools=runtime_tools,
        resources=runtime_resources,
        prompts=runtime_prompts,
        fl_capabilities=capability_catalog(),
        provider_matrix=PROVIDER_MATRIX,
        provider_count=len(provider_registry.manifests()),
        providers=provider_registry.statuses(),
    )
    return response.model_dump()


def manage_providers(
    action: str = "list",
    module: str | None = None,
    group: str = "fl_mcp.providers",
) -> dict[str, object]:
    """List or manage provider lifecycle without public dynamic loading.

    Args:
        action: One of "list", "discover", "load_module", "startup", "shutdown".
            Public callers can use "list", "startup", and "shutdown"; dynamic loading
            actions return explicit errors.
        module: Python module path (unused on the public surface when action is
            "load_module").
        group: Entry-point group used during discovery (unused on the public surface
            when action is "discover").

    Returns:
        Serialized ManageProvidersResponse dict.
    """
    logger.info("manage_providers: action=%s", action)
    try:
        provider_registry = get_provider_registry(load_entry_points=False)

        if action in _DISABLED_PUBLIC_PROVIDER_ACTION_ERRORS:
            return ManageProvidersResponse(
                status="error",
                action=action,
                error=_DISABLED_PUBLIC_PROVIDER_ACTION_ERRORS[action],
                provider_count=len(provider_registry.manifests()),
                providers=_provider_statuses(),
            ).model_dump()

        if action == "startup":
            started = provider_registry.startup_all()
            return ManageProvidersResponse(
                status="ok",
                action=action,
                started=started,
                provider_count=len(provider_registry.manifests()),
                providers=_provider_statuses(),
            ).model_dump()
        if action == "shutdown":
            stopped = provider_registry.shutdown_all()
            return ManageProvidersResponse(
                status="ok",
                action=action,
                stopped=stopped,
                provider_count=len(provider_registry.manifests()),
                providers=_provider_statuses(),
            ).model_dump()
        if action not in _PUBLIC_PROVIDER_ACTIONS:
            return ManageProvidersResponse(
                status="error",
                action=action,
                error=(
                    f"unsupported provider action: {action}; "
                    "allowed actions: list, startup, shutdown"
                ),
                provider_count=len(provider_registry.manifests()),
                providers=_provider_statuses(),
            ).model_dump()
        return ManageProvidersResponse(
            status="ok",
            action="list",
            provider_count=len(provider_registry.manifests()),
            providers=_provider_statuses(),
        ).model_dump()
    except Exception as exc:
        logger.warning("Error in manage_providers (action=%s): %s", action, exc, exc_info=True)
        return {"status": "error", "tool": "manage_providers", "error": str(exc)}
