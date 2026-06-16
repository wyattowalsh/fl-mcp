"""Compact FastMCP tool surface backed by the full FL operation catalog."""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE, default_provider_for_operation
from fl_mcp.bridge.live_surface import (
    forced_live_flapi_supports,
    live_flapi_supports,
)
from fl_mcp.config import RuntimeConfig
from fl_mcp.exceptions import ProviderError
from fl_mcp.graph.model import ProjectGraph
from fl_mcp.plugin_profiles.operations import (
    PROFILE_OPERATION_ID_SET,
    is_plugin_profile_operation,
)
from fl_mcp.plugin_profiles.registry import get_plugin_profile_registry
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.resources import surface as surface_resources
from fl_mcp.runtime.health import health_payload
from fl_mcp.runtime.state import get_runtime_state
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.schemas.compact_surface import (
    BatchPolicy,
    BrowserAction,
    BrowserKind,
    CapabilityReadbackRequest,
    CapabilitySafetyModel,
    CapabilitySchemaResponse,
    CapabilitySearchResponse,
    CapabilitySummaryModel,
    FLApplyResponse,
    FLBatchExecuteResponse,
    FLBatchOperationRequest,
    FLBrowserResponse,
    FLExecuteResponse,
    FLPlanResponse,
    FLProviderManagementResponse,
    FLSnapshotResponse,
    FLStatusResponse,
    FLTaskEntryResponse,
    ProviderSupportModel,
    ReadbackPolicy,
)
from fl_mcp.schemas.fl_tools import AudioAnalyzeRequest, RenderExportRequest
from fl_mcp.tools import public
from fl_mcp.tools.fl_surface import (
    FL_TOOL_HANDLERS,
    FL_TOOL_SPECS,
    PROVIDER_MATRIX,
    FLToolSpec,
)

logger = logging.getLogger(__name__)

COMPACT_TOOL_NAMES: tuple[str, ...] = (
    "fl_status",
    "fl_snapshot",
    "fl_search_capabilities",
    "fl_get_capability_schema",
    "fl_execute",
    "fl_batch_execute",
    "fl_plan",
    "fl_apply",
    "fl_render",
    "fl_analyze_audio",
    "fl_manage_providers",
    "fl_browser",
)

BROWSER_OPERATION_IDS: tuple[str, ...] = (
    "plugins.list_plugins",
    "plugins.load",
    "plugins.replace",
    "plugins.next_preset",
    "plugins.prev_preset",
    "plugins.get_preset_name",
    "plugins.load_preset_by_name",
    "plugins.get_parameter_name",
    "plugins.inventory_scan",
    "plugins.list_profiles",
    "plugins.get_profile",
    "plugins.resolve_profile",
    "plugins.probe_instance",
    "plugins.enumerate_parameters",
    "plugins.probe_loadability",
    "plugins.generate_raw_profile",
    "plugins.learn_parameter",
    "plugins.validate_profile",
    "plugins.verify_profile_controls",
    "plugins.write_calibration_overlay",
    "plugins.get_mapped_parameter",
    "plugins.set_mapped_parameter",
    "plugins.load_profile_preset",
    "plugins.list_local_presets",
    "plugins.reconcile_inventory",
    "plugins.priority_support_audit",
    "plugins.export_support_matrix",
    "channels.load_sample",
    "patterns.create_pattern",
    "piano-roll.generate_chords",
    "piano-roll.generate_melody",
    "piano-roll.generate_bass",
    "playlist.place_clip",
    "ui.show_window",
)

_OPERATION_BY_ID: dict[str, FLToolSpec] = {
    f"{spec.domain}.{spec.operation}": spec for spec in FL_TOOL_SPECS
}


def operation_id_for_spec(spec: FLToolSpec) -> str:
    """Return the canonical compact-surface operation id for a spec."""

    return f"{spec.domain}.{spec.operation}"


def operation_ids() -> tuple[str, ...]:
    """Return all compact operation ids in catalog order."""

    return tuple(operation_id_for_spec(spec) for spec in FL_TOOL_SPECS)


def _resolve_operation(operation_id: str) -> FLToolSpec:
    spec = _OPERATION_BY_ID.get(operation_id)
    if spec is None:
        msg = f"unknown operation_id: {operation_id}"
        raise KeyError(msg)
    return spec


def _providers_for_spec(spec: FLToolSpec) -> list[str]:
    return sorted(detail.provider for detail in _provider_support_for_spec(spec))


def _provider_capability_name(spec: FLToolSpec) -> str:
    return f"{spec.domain}_{spec.operation}".replace("-", "_")


def _provider_manifest_supports_spec(metadata: dict[str, object], spec: FLToolSpec) -> bool:
    operation_id = operation_id_for_spec(spec)
    capabilities = cast(list[str], metadata.get("capabilities", []))
    return (
        "all" in capabilities
        or spec.name in capabilities
        or _provider_capability_name(spec) in capabilities
        or operation_id in capabilities
    )


def _readback_operation_id_for_spec(spec: FLToolSpec) -> str | None:
    if spec.annotations.get("readOnlyHint"):
        return None
    candidates: list[str] = []
    if spec.operation.startswith("set_"):
        candidates.append(f"{spec.domain}.get_{spec.operation.removeprefix('set_')}")
    if spec.operation.startswith("update_"):
        candidates.append(f"{spec.domain}.get_{spec.operation.removeprefix('update_')}")
    for candidate in candidates:
        if candidate in _OPERATION_BY_ID:
            return candidate
    return None


def _provider_support_for_spec(spec: FLToolSpec) -> list[ProviderSupportModel]:
    details: list[ProviderSupportModel] = []
    registry = get_provider_registry(load_entry_points=False)
    manifest_metadata = {manifest.name: manifest.model_dump() for manifest in registry.manifests()}
    provider_names = sorted(set(PROVIDER_MATRIX) | set(manifest_metadata))
    for name in provider_names:
        metadata = cast(dict[str, object], manifest_metadata.get(name) or PROVIDER_MATRIX[name])
        if not _provider_manifest_supports_spec(metadata, spec):
            continue
        readback_operation_id = _readback_operation_id_for_spec(spec)
        if name == "mock":
            details.append(
                ProviderSupportModel(
                    provider=name,
                    status="mock_only",
                    mode="mock",
                    preconditions=[
                        "caller explicitly requests provider=mock or runtime is in mock mode"
                    ],
                    readback_operation_id=readback_operation_id,
                    failure_policy="deterministic_mock_only",
                )
            )
            continue
        if name == "flapi-live" and live_flapi_supports(spec.domain, spec.operation):
            details.append(
                ProviderSupportModel(
                    provider=name,
                    status="available",
                    mode="host_file_bridge",
                    preconditions=[
                        "FL_MCP_BRIDGE_MODE=live",
                        "FL_MCP_FL_STUDIO_BRIDGE_CMD points at the trusted host-file bridge",
                    ],
                    readback_operation_id=readback_operation_id,
                    failure_policy="attempt_live_then_structured_error",
                )
            )
            continue
        if name == "flapi-live" and forced_live_flapi_supports(spec.domain, spec.operation):
            details.append(
                ProviderSupportModel(
                    provider=name,
                    status="attemptable",
                    mode="host_file_bridge",
                    preconditions=[
                        "FL_MCP_BRIDGE_MODE=live",
                        "FL_MCP_FL_STUDIO_BRIDGE_CMD points at the bundled FL MCP Bridge",
                    ],
                    readback_operation_id=readback_operation_id,
                    failure_policy="attempt_live_then_structured_error",
                )
            )
            continue
        details.append(
            ProviderSupportModel(
                provider=name,
                status="requires_setup",
                mode="custom_provider",
                preconditions=["registered provider adapter must implement this exact operation"],
                readback_operation_id=readback_operation_id,
                failure_policy="fail_closed_without_adapter_support",
            )
        )
    return sorted(details, key=lambda item: item.provider)


def _safety_for_spec(spec: FLToolSpec) -> CapabilitySafetyModel:
    annotations = dict(spec.annotations)
    read_only = bool(annotations.get("readOnlyHint"))
    destructive = bool(annotations.get("destructiveHint"))
    idempotent = bool(annotations.get("idempotentHint"))
    guidance = (
        "Read-only operation; readback is normally unnecessary."
        if read_only
        else "Use readback after execution for state-changing operations."
    )
    if destructive:
        guidance = "Destructive operation; plan first and use readback or rollback policy."
    return CapabilitySafetyModel(
        read_only=read_only,
        destructive=destructive,
        idempotent=idempotent,
        open_world=bool(annotations.get("openWorldHint", True)),
        rollback_class=str(spec.rollback_class) if spec.rollback_class is not None else None,
        readback_guidance=guidance,
    )


def _summary_for_spec(spec: FLToolSpec) -> CapabilitySummaryModel:
    support_details = _provider_support_for_spec(spec)
    return CapabilitySummaryModel(
        operation_id=operation_id_for_spec(spec),
        tool_name=spec.name,
        domain=spec.domain,
        operation=spec.operation,
        description=spec.description,
        tags=sorted(set(spec.tags)),
        providers=sorted(detail.provider for detail in support_details),
        provider_support_details=support_details,
        default_provider=_default_provider_for_spec(spec),
        execution_mode=spec.execution_mode,
        request_model=spec.request_model.__name__,
        response_model=spec.response_model.__name__,
        task=spec.task,
        timeout=spec.timeout,
        safety=_safety_for_spec(spec),
        example_request=example_request_for_spec(spec),
    )


def _is_required_field(field: Any) -> bool:
    return field.default is PydanticUndefined and field.default_factory is None


def _sample_for_field(name: str, annotation: object) -> object:
    if name in {"track_index", "channel_index", "pattern_index", "arrangement_index"}:
        return 0
    if name in {"slot_index", "clip_index", "target_index", "parameter_index", "band"}:
        return 0
    if name == "profile_id":
        return "lennardigital.sylenth1"
    if name == "control_id":
        return "filter.cutoff"
    if name == "plugin_format":
        return "vst3"
    if name == "fingerprint":
        return "mock-fingerprint"
    if name == "observed_parameter_index":
        return 0
    if name in {"include_paths", "include_presets", "include_inventory", "include_calibration"}:
        return False if name == "include_paths" else True
    if name in {"destination_track_index", "mixer_track_index"}:
        return 0
    if name == "note":
        return 60
    if name in {"velocity", "control", "program"}:
        return 100 if name == "velocity" else 1
    if name == "value":
        return 0
    if name == "bpm":
        return 120.0
    if name == "speed":
        return 1.0
    if name in {"position_beats", "start_beats", "destination_start_beats"}:
        return 0.0
    if name in {"duration_beats", "length_beats"}:
        return 4.0
    if name in {"pitch", "stereo_separation"}:
        return 0.0
    if name == "semitones":
        return 0
    if name in {"numerator", "denominator"}:
        return 4
    if name == "mode":
        return "song"
    if name == "window":
        return "browser"
    if name == "target_type":
        return "mixer"
    if name == "source":
        return "pattern:0"
    if name == "name":
        return "Agent Pattern"
    if name == "plugin_name":
        return "FLEX"
    if name == "preset_name":
        return "Default"
    if name == "preset_path":
        return "mock://preset.fxp"
    if name == "parameter":
        return "volume"
    if name == "file_path":
        return "mock://sample.wav"
    if name == "path":
        return "mock://project.flp"
    if name == "output_path":
        return "mock://render.wav"
    if name == "input_path":
        return "mock://render.wav"
    if name == "job_id":
        return "mock-job"
    if name == "analysis_id":
        return "mock-analysis"
    if name == "points":
        return [{"position_beats": 0.0, "value": 0.5}]
    if name == "enabled":
        return True

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list:
        return []
    if args and all(isinstance(item, str) for item in args):
        return args[0]
    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is str:
        return "mock"
    return None


def example_request_for_spec(spec: FLToolSpec) -> dict[str, object]:
    """Build a conservative example request accepted by the operation model."""

    payload: dict[str, object] = {}
    for name, field in spec.request_model.model_fields.items():
        if name in {"provider", "session_label"}:
            continue
        if _is_required_field(field):
            value = _sample_for_field(name, field.annotation)
            if value is not None:
                payload[name] = value
    try:
        return spec.request_model.model_validate(payload).model_dump(exclude_none=True)
    except ValidationError:
        logger.debug("generated example failed for %s", spec.name, exc_info=True)
        return payload


def _coerce_request_payload(request: dict[str, object] | BaseModel | None) -> dict[str, object]:
    if request is None:
        return {}
    if isinstance(request, BaseModel):
        return cast(dict[str, object], request.model_dump(exclude_none=True))
    return dict(request)


def _task_id_from_result(result: dict[str, object]) -> str | None:
    task = result.get("task")
    if isinstance(task, dict):
        task_payload = cast(dict[str, object], task)
        task_id = task_payload.get("id")
        if isinstance(task_id, str):
            return task_id
    nested_result = result.get("result")
    if isinstance(nested_result, dict):
        nested_task_id = _task_id_from_result(cast(dict[str, object], nested_result))
        if nested_task_id is not None:
            return nested_task_id
    for key in ("job_id", "analysis_id", "task_id"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return None


def _transaction_payload(result: dict[str, object]) -> dict[str, object] | None:
    transaction = result.get("transaction")
    return cast(dict[str, object], transaction) if isinstance(transaction, dict) else None


def _first_transaction_report(result: dict[str, object]) -> dict[str, object] | None:
    transaction = _transaction_payload(result)
    if transaction is None:
        return None
    diff_summary = transaction.get("diff_summary")
    if not isinstance(diff_summary, dict):
        return None
    reports = diff_summary.get("reports")
    if not isinstance(reports, list) or not reports:
        return None
    report = reports[0]
    return cast(dict[str, object], report) if isinstance(report, dict) else None


def _count_from_transaction(transaction: dict[str, object], key: str) -> int:
    diff_summary = transaction.get("diff_summary")
    if not isinstance(diff_summary, dict):
        return 0
    value = diff_summary.get(key)
    return value if isinstance(value, int) else 0


def _status_from_result(result: dict[str, object]) -> str:
    status = result.get("status")
    if status in {"ok", "partial", "error"}:
        return cast(str, status)
    if status == "failed":
        return "error"
    if status == "partially_applied":
        return "partial"
    if status in {"applied", "planned", "queued"}:
        return "ok"

    transaction = _transaction_payload(result)
    if transaction is not None:
        transaction_status = transaction.get("status")
        failed_count = _count_from_transaction(transaction, "failed_count")
        applied_count = _count_from_transaction(transaction, "applied_count")
        if transaction_status == "failed" or (failed_count > 0 and applied_count == 0):
            return "error"
        if transaction_status == "partially_applied" or failed_count > 0:
            return "partial"
        if transaction_status in {"applied", "planned"}:
            return "ok"

    return "error" if result.get("error") else "ok"


def _provider_from_result(result: dict[str, object]) -> str | None:
    provider = result.get("provider")
    if isinstance(provider, str):
        return provider
    report = _first_transaction_report(result)
    if report is None:
        return None
    report_provider = report.get("provider")
    return report_provider if isinstance(report_provider, str) else None


def _execution_id_from_result(result: dict[str, object]) -> str | None:
    execution_id = result.get("execution_id")
    if isinstance(execution_id, str):
        return execution_id
    report = _first_transaction_report(result)
    if report is None:
        return None
    report_execution_id = report.get("execution_id")
    return report_execution_id if isinstance(report_execution_id, str) else None


def _error_from_result(result: dict[str, object]) -> str | None:
    error = result.get("error")
    if isinstance(error, str):
        return error
    transaction = _transaction_payload(result)
    if transaction is not None:
        errors = transaction.get("errors")
        if isinstance(errors, list):
            messages = [item for item in errors if isinstance(item, str) and item]
            if messages:
                return "; ".join(messages)
    report = _first_transaction_report(result)
    if report is not None:
        report_success = report.get("success")
        report_error_code = report.get("error_code")
        message = report.get("message")
        if (
            isinstance(message, str)
            and message
            and (report_success is False or isinstance(report_error_code, str))
        ):
            return message
    message = result.get("message")
    return message if isinstance(message, str) and _status_from_result(result) == "error" else None


def _coerce_readback(
    readback: CapabilityReadbackRequest | dict[str, object] | None,
) -> CapabilityReadbackRequest | None:
    if readback is None:
        return None
    if isinstance(readback, CapabilityReadbackRequest):
        return readback
    return CapabilityReadbackRequest.model_validate(readback)


def _normalize_provider_filter(provider: str | None) -> tuple[str | None, str | None]:
    if provider is None or provider == "auto":
        return None, None
    registry = get_provider_registry(load_entry_points=False)
    canonical = registry.resolve_name(provider)
    try:
        registry.get(canonical)
    except ProviderError:
        return None, f"unknown provider filter: {provider}"
    return canonical, None


def _default_provider_for_spec(spec: FLToolSpec) -> str:
    if DEFAULT_BRIDGE.mode == "live" and forced_live_flapi_supports(spec.domain, spec.operation):
        return "flapi-live"
    return default_provider_for_operation(spec.domain, spec.operation)


def _resolve_execution_provider(spec: FLToolSpec, provider: str, payload: dict[str, object]) -> str:
    requested = provider if provider != "auto" else str(payload.get("provider", "auto"))
    if requested and requested != "auto":
        registry = get_provider_registry(load_entry_points=False)
        canonical = registry.resolve_name(str(requested))
        registry.get(canonical)
        return canonical
    if DEFAULT_BRIDGE.mode == "live" and forced_live_flapi_supports(spec.domain, spec.operation):
        return "flapi-live"
    return default_provider_for_operation(spec.domain, spec.operation)


def _provider_result_payload(
    *,
    spec: FLToolSpec,
    provider_result: Any,
) -> dict[str, object]:
    status = "ok" if bool(provider_result.success) else "error"
    return {
        "status": status,
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "provider": provider_result.provider,
        "bridge_mode": provider_result.bridge_mode,
        "execution_id": provider_result.execution_id,
        "message": provider_result.message,
        "error": provider_result.message if not bool(provider_result.success) else None,
        "error_code": provider_result.error_code,
        "result": provider_result.result,
    }


def _live_auto_mock_fallback_error(
    spec: FLToolSpec, provider_name: str
) -> FLExecuteResponse | None:
    if provider_name != "mock" or DEFAULT_BRIDGE.mode != "live":
        return None
    return FLExecuteResponse(
        status="error",
        operation_id=operation_id_for_spec(spec),
        provider="auto",
        bridge_mode=DEFAULT_BRIDGE.mode,
        operation=_summary_for_spec(spec),
        result={
            "status": "error",
            "error_code": "live_provider_unavailable",
            "message": (
                f"Live runtime has no non-mock provider for {spec.domain}.{spec.operation}. "
                "Request provider=mock explicitly for rehearsal, or register a "
                "live/custom provider."
            ),
            "provider_support_details": [
                item.model_dump(mode="json") for item in _provider_support_for_spec(spec)
            ],
        },
        error="live_provider_unavailable",
    )


def _execute_operation(
    operation_id: str,
    request: dict[str, object] | BaseModel | None = None,
    *,
    provider: str = "auto",
    readback: CapabilityReadbackRequest | dict[str, object] | None = None,
) -> FLExecuteResponse:
    spec = _resolve_operation(operation_id)
    payload = _coerce_request_payload(request)
    if provider and provider != "auto":
        payload["provider"] = provider

    validated = spec.request_model.model_validate(payload)
    resolved_provider = _resolve_execution_provider(spec, provider, payload)
    fallback_error = _live_auto_mock_fallback_error(spec, resolved_provider)
    if (
        fallback_error is not None
        and provider == "auto"
        and payload.get("provider", "auto") == "auto"
    ):
        return fallback_error

    use_profile_runtime_handler = is_plugin_profile_operation(
        spec.domain, spec.operation
    ) and resolved_provider in {"mock", "flapi-live"}
    if use_profile_runtime_handler:
        result = dict(FL_TOOL_HANDLERS[spec.name](validated))
    elif resolved_provider != "mock":
        registry = get_provider_registry(load_entry_points=False)
        provider_result = registry.execute(
            resolved_provider,
            domain=spec.domain,
            operation=spec.operation,
            payload=validated.model_dump(exclude_none=True, exclude={"provider", "session_label"}),
        )
        result = _provider_result_payload(spec=spec, provider_result=provider_result)
    else:
        result = dict(FL_TOOL_HANDLERS[spec.name](validated))
    readback_request = _coerce_readback(readback)
    readback_result: dict[str, object] | None = None
    if readback_request is not None:
        readback_result = _execute_operation(
            readback_request.operation_id,
            readback_request.request,
            provider=readback_request.provider,
        ).model_dump(exclude_none=True)

    return FLExecuteResponse(
        status=cast(Any, _status_from_result(result)),
        operation_id=operation_id,
        provider=_provider_from_result(result),
        bridge_mode=cast(str | None, result.get("bridge_mode")),
        execution_id=_execution_id_from_result(result),
        task_id=_task_id_from_result(result),
        operation=_summary_for_spec(spec),
        result=result,
        readback=readback_result,
        error=_error_from_result(result),
    )


def fl_status(runtime_config: RuntimeConfig | None = None) -> dict[str, object]:
    """Return runtime, provider, bridge, task, and catalog health."""

    config = runtime_config or RuntimeConfig()
    health = health_payload(config)
    registry = get_provider_registry(load_entry_points=False)
    runtime_state = get_runtime_state()
    domain_counts = Counter(spec.domain for spec in FL_TOOL_SPECS)
    payload = FLStatusResponse(
        status=cast(Any, health.get("status", "ok")),
        runtime={
            "service": health.get("service"),
            "version": health.get("version"),
            "environment": health.get("environment"),
            "fastmcp_surface": "compact",
        },
        connection=cast(dict[str, object], surface_resources.provider_matrix()["data"]),
        capabilities={
            "visible_tool_count": len(COMPACT_TOOL_NAMES),
            "internal_operation_count": len(FL_TOOL_SPECS),
            "domain_count": len(domain_counts),
            "domains": dict(sorted(domain_counts.items())),
        },
        providers=[dict(status) for status in registry.statuses()],
        bridge={
            "mode": "provider-routed",
            "default_provider_matrix_size": len(PROVIDER_MATRIX),
        },
        tasks={
            "render_jobs": len(runtime_state.render_jobs),
            "audio_analyses": len(runtime_state.audio_analyses),
        },
    )
    return payload.model_dump(mode="json", exclude_none=True)


def fl_snapshot(
    domain: str = "project",
    graph: dict[str, object] | None = None,
) -> dict[str, object]:
    """Read project/session/domain state through the resource-first snapshot path."""

    try:
        if domain in {"project", "snapshot", "all"}:
            data = {
                "project": surface_resources.project_snapshot()["data"],
                "arrangement": surface_resources.project_arrangement()["data"],
                "capabilities": surface_resources.runtime_capabilities()["data"],
            }
        elif domain == "arrangement":
            data = cast(dict[str, object], surface_resources.project_arrangement()["data"])
        elif domain == "capabilities":
            data = cast(dict[str, object], surface_resources.runtime_capabilities()["data"])
        else:
            graph_override: ProjectGraph | dict[str, object] | None = graph
            data = public.query_project(domain, graph_override)
        return FLSnapshotResponse(status="ok", domain=domain, data=data).model_dump(
            mode="json", exclude_none=True
        )
    except Exception as exc:
        logger.warning("fl_snapshot failed for domain=%s: %s", domain, exc, exc_info=True)
        return FLSnapshotResponse(status="error", domain=domain, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower().replace("_", " ").replace("-", " "))


def _search_score(query: str, summary: CapabilitySummaryModel) -> int:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 1
    haystack = " ".join(
        [
            summary.operation_id,
            summary.tool_name,
            summary.domain,
            summary.operation,
            summary.description,
            " ".join(summary.tags),
            " ".join(summary.providers),
        ]
    )
    haystack_tokens = set(_tokens(haystack))
    score = 0
    for token in query_tokens:
        if token in haystack_tokens:
            score += 4
            continue
        if any(token in candidate or candidate in token for candidate in haystack_tokens):
            score += 1
        else:
            return 0
    if query.lower() in haystack.lower():
        score += 8
    return score


def fl_search_capabilities(
    query: str | None = None,
    domain: str | None = None,
    provider: str | None = None,
    read_only: bool | None = None,
    destructive: bool | None = None,
    task: bool | None = None,
    limit: int = 25,
) -> dict[str, object]:
    """Search the hidden FL operation catalog by intent, domain, provider, or safety."""

    normalized_query = (query or "").strip().lower()
    provider_filter, provider_error = _normalize_provider_filter(provider)
    if provider_error is not None:
        bounded_limit = max(1, min(limit, 100))
        return CapabilitySearchResponse(
            status="error",
            total=0,
            count=0,
            query=query,
            filters={
                "domain": domain,
                "provider": provider,
                "read_only": read_only,
                "destructive": destructive,
                "task": task,
                "limit": bounded_limit,
            },
            error=provider_error,
        ).model_dump(mode="json", exclude_none=True)

    ranked_results: list[tuple[int, int, CapabilitySummaryModel]] = []
    for spec in FL_TOOL_SPECS:
        summary = _summary_for_spec(spec)
        score = _search_score(normalized_query, summary)
        if normalized_query and score <= 0:
            continue
        if domain and summary.domain != domain:
            continue
        if provider_filter and provider_filter not in summary.providers:
            continue
        if read_only is not None and summary.safety.read_only is not read_only:
            continue
        if destructive is not None and summary.safety.destructive is not destructive:
            continue
        if task is not None and summary.task is not task:
            continue
        ranked_results.append((score, len(ranked_results), summary))

    results = [item[2] for item in sorted(ranked_results, key=lambda item: (-item[0], item[1]))]
    bounded_limit = max(1, min(limit, 100))
    response = CapabilitySearchResponse(
        status="ok",
        total=len(results),
        count=min(len(results), bounded_limit),
        query=query,
        filters={
            "domain": domain,
            "provider": provider,
            "read_only": read_only,
            "destructive": destructive,
            "task": task,
            "limit": bounded_limit,
        },
        results=results[:bounded_limit],
    )
    return response.model_dump(mode="json", exclude_none=True)


def _profile_operation_schema_metadata(operation_id: str) -> dict[str, object] | None:
    if operation_id not in PROFILE_OPERATION_ID_SET:
        return None
    registry = get_plugin_profile_registry()
    profile = registry.profile("lennardigital.sylenth1")
    inventory = registry.inventory_item("lennardigital.sylenth1")
    trash = registry.inventory_item("izotope.trash")
    return {
        "profile_support": "declarative_profile_plus_local_calibration",
        "calibration_policy": "semantic controls require local FL parameter indices before writes",
        "failure_policy": "fail_closed_with_structured_error",
        "example_profile": profile.model_dump(mode="json") if profile is not None else None,
        "example_inventory_status": inventory.status if inventory is not None else "unknown",
        "desired_target_status": {
            "izotope.trash": trash.status if trash is not None else "not_installed"
        },
    }


def fl_get_capability_schema(operation_id: str) -> dict[str, object]:
    """Return exact request/response schemas and execution guidance for an operation."""

    try:
        spec = _resolve_operation(operation_id)
        summary = _summary_for_spec(spec)
        example: dict[str, object] = {
            "operation_id": operation_id,
            "request": summary.example_request,
            "provider": "auto",
        }
        profile_metadata = _profile_operation_schema_metadata(operation_id)
        if profile_metadata is not None:
            example["plugin_profile_metadata"] = profile_metadata
        response = CapabilitySchemaResponse(
            status="ok",
            operation_id=operation_id,
            capability=summary,
            request_schema=spec.request_model.model_json_schema(),
            response_schema=spec.response_model.model_json_schema(),
            examples=[example],
            provider_support=summary.providers,
            provider_support_details=summary.provider_support_details,
        )
        return response.model_dump(mode="json", exclude_none=True)
    except KeyError as exc:
        return CapabilitySchemaResponse(
            status="error",
            operation_id=operation_id,
            error=str(exc),
        ).model_dump(mode="json", exclude_none=True)


def fl_execute(
    operation_id: str,
    request: dict[str, object] | None = None,
    provider: str = "auto",
    readback: CapabilityReadbackRequest | dict[str, object] | None = None,
) -> dict[str, object]:
    """Execute one typed FL operation by canonical operation id."""

    try:
        return _execute_operation(
            operation_id,
            request,
            provider=provider,
            readback=readback,
        ).model_dump(mode="json", exclude_none=True)
    except (KeyError, ProviderError, ValidationError, TypeError) as exc:
        logger.warning("fl_execute failed for %s: %s", operation_id, exc, exc_info=True)
        return FLExecuteResponse(
            status="error",
            operation_id=operation_id,
            error=str(exc),
        ).model_dump(mode="json", exclude_none=True)


def _default_readback_for_operation(
    operation: FLBatchOperationRequest,
) -> CapabilityReadbackRequest | None:
    try:
        spec = _resolve_operation(operation.operation_id)
    except KeyError:
        return None
    if spec.annotations.get("readOnlyHint"):
        return None
    candidates: list[str] = []
    if spec.operation.startswith("set_"):
        candidates.append(f"{spec.domain}.get_{spec.operation.removeprefix('set_')}")
    if spec.operation.startswith("update_"):
        candidates.append(f"{spec.domain}.get_{spec.operation.removeprefix('update_')}")
    if spec.operation.startswith("create_"):
        candidates.append(
            "patterns.list_patterns" if spec.domain == "patterns" else f"{spec.domain}.list"
        )
    for candidate in candidates:
        candidate_spec = _OPERATION_BY_ID.get(candidate)
        if candidate_spec is None:
            continue
        readback_payload: dict[str, object] = {}
        for field_name in candidate_spec.request_model.model_fields:
            if field_name in {"provider", "session_label"}:
                continue
            if field_name in operation.request:
                readback_payload[field_name] = operation.request[field_name]
                continue
            if field_name == "track_index" and "index" in operation.request:
                readback_payload[field_name] = operation.request["index"]
                continue
            if field_name == "index" and "track_index" in operation.request:
                readback_payload[field_name] = operation.request["track_index"]
                continue
        try:
            candidate_spec.request_model.model_validate(
                {**readback_payload, "provider": operation.provider}
            )
        except ValidationError:
            logger.debug("generated readback failed for %s", candidate, exc_info=True)
            continue
        return CapabilityReadbackRequest(
            operation_id=candidate,
            request=readback_payload,
            provider=operation.provider,
        )
    return None


def fl_batch_execute(
    operations: list[FLBatchOperationRequest | dict[str, object]],
    policy: BatchPolicy = "stop-on-error",
    readback_policy: ReadbackPolicy = "none",
) -> dict[str, object]:
    """Execute an ordered operation batch with optional readback."""

    results: list[dict[str, object]] = []
    failed = 0
    succeeded = 0
    try:
        normalized_operations = [
            item
            if isinstance(item, FLBatchOperationRequest)
            else FLBatchOperationRequest.model_validate(item)
            for item in operations
        ]
    except ValidationError as exc:
        return FLBatchExecuteResponse(
            status="error",
            policy=policy,
            readback_policy=readback_policy,
            total=len(operations),
            succeeded=0,
            failed=len(operations),
            error=str(exc),
        ).model_dump(mode="json", exclude_none=True)

    deferred_readbacks: list[tuple[int, CapabilityReadbackRequest]] = []
    for index, operation in enumerate(normalized_operations):
        readback = operation.readback
        if readback is None and readback_policy in {"after_each", "after_batch"}:
            readback = _default_readback_for_operation(operation)
        execute_readback = readback
        if readback is not None and readback_policy == "after_batch" and operation.readback is None:
            deferred_readbacks.append((index, readback))
            execute_readback = None
        response = fl_execute(
            operation.operation_id,
            operation.request,
            provider=operation.provider,
            readback=execute_readback,
        )
        response["index"] = index
        if operation.label is not None:
            response["label"] = operation.label
        results.append(response)
        if response.get("status") == "error":
            failed += 1
            if policy == "stop-on-error":
                break
        else:
            succeeded += 1

    if readback_policy == "after_batch":
        for index, readback in deferred_readbacks:
            if index >= len(results) or results[index].get("status") == "error":
                continue
            readback_response = fl_execute(
                readback.operation_id,
                readback.request,
                provider=readback.provider,
            )
            results[index]["readback"] = readback_response
            if readback_response.get("status") == "error":
                results[index]["status"] = "error"
                results[index]["error"] = readback_response.get("error", "readback failed")
                failed += 1
                succeeded = max(0, succeeded - 1)

    status = "ok" if failed == 0 else ("partial" if succeeded else "error")
    return FLBatchExecuteResponse(
        status=cast(Any, status),
        policy=policy,
        readback_policy=readback_policy,
        total=len(normalized_operations),
        succeeded=succeeded,
        failed=failed,
        results=results,
    ).model_dump(mode="json", exclude_none=True)


def fl_plan(envelope: dict[str, object] | TransactionEnvelope) -> dict[str, object]:
    """Preview transaction/batch changes using the transaction planner."""

    try:
        model = (
            envelope
            if isinstance(envelope, TransactionEnvelope)
            else TransactionEnvelope.model_validate(envelope)
        )
        result = public.plan_changes(model)
        status = "error" if result.get("status") == "error" else "ok"
        return FLPlanResponse(status=cast(Any, status), result=result).model_dump(
            mode="json", exclude_none=True
        )
    except (ProviderError, ValidationError, TypeError) as exc:
        return FLPlanResponse(status="error", error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )


def fl_apply(envelope: dict[str, object] | TransactionEnvelope) -> dict[str, object]:
    """Apply planned/typed changes using transaction rollback/readback policy."""

    try:
        model = (
            envelope
            if isinstance(envelope, TransactionEnvelope)
            else TransactionEnvelope.model_validate(envelope)
        )
        result = public.apply_changes(model)
        status = "error" if result.get("status") == "error" else "ok"
        return FLApplyResponse(status=cast(Any, status), result=result).model_dump(
            mode="json", exclude_none=True
        )
    except (ProviderError, ValidationError, TypeError) as exc:
        return FLApplyResponse(status="error", error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )


def fl_render(request: RenderExportRequest | dict[str, object] | None = None) -> dict[str, object]:
    """Queue a render/export task through the compact surface."""

    payload = (
        request
        if isinstance(request, RenderExportRequest)
        else RenderExportRequest.model_validate(request or {})
    )
    if payload.provider != "mock" and (payload.provider != "auto" or DEFAULT_BRIDGE.mode == "live"):
        executed = _execute_operation(
            "render.export",
            payload.model_dump(exclude_none=True, exclude={"session_label"}),
            provider=payload.provider,
        ).model_dump(mode="json", exclude_none=True)
        status = "error" if executed.get("status") == "error" else "ok"
        return FLTaskEntryResponse(
            status=cast(Any, status),
            tool="fl_render",
            result=executed,
            task_id=_task_id_from_result(executed),
            error=cast(str | None, executed.get("error")),
        ).model_dump(mode="json", exclude_none=True)
    if payload.provider == "auto":
        payload = payload.model_copy(update={"provider": "mock"})
    result = public.render_project(payload)
    status = "error" if result.get("status") == "error" else "ok"
    return FLTaskEntryResponse(
        status=cast(Any, status),
        tool="fl_render",
        result=result,
        task_id=_task_id_from_result(result),
        error=cast(str | None, result.get("error")),
    ).model_dump(mode="json", exclude_none=True)


def fl_analyze_audio(
    request: AudioAnalyzeRequest | dict[str, object] | None = None,
) -> dict[str, object]:
    """Queue an audio analysis task through the compact surface."""

    payload = (
        request
        if isinstance(request, AudioAnalyzeRequest)
        else AudioAnalyzeRequest.model_validate(request or {})
    )
    if payload.provider != "mock" and (payload.provider != "auto" or DEFAULT_BRIDGE.mode == "live"):
        executed = _execute_operation(
            "audio.analyze",
            payload.model_dump(exclude_none=True, exclude={"session_label"}),
            provider=payload.provider,
        ).model_dump(mode="json", exclude_none=True)
        status = "error" if executed.get("status") == "error" else "ok"
        return FLTaskEntryResponse(
            status=cast(Any, status),
            tool="fl_analyze_audio",
            result=executed,
            task_id=_task_id_from_result(executed),
            error=cast(str | None, executed.get("error")),
        ).model_dump(mode="json", exclude_none=True)
    if payload.provider == "auto":
        payload = payload.model_copy(update={"provider": "mock"})
    result = public.analyze_audio(payload)
    status = "error" if result.get("status") == "error" else "ok"
    return FLTaskEntryResponse(
        status=cast(Any, status),
        tool="fl_analyze_audio",
        result=result,
        task_id=_task_id_from_result(result),
        error=cast(str | None, result.get("error")),
    ).model_dump(mode="json", exclude_none=True)


def fl_manage_providers(
    action: str = "list",
    module: str | None = None,
    group: str = "fl_mcp.providers",
) -> dict[str, object]:
    """Inspect provider lifecycle and routing from the compact surface."""

    result = public.manage_providers(action=action, module=module, group=group)
    status = "error" if result.get("status") == "error" else "ok"
    return FLProviderManagementResponse(
        status=cast(Any, status),
        result=result,
        error=cast(str | None, result.get("error")),
    ).model_dump(mode="json", exclude_none=True)


def _browser_operation_ids(kind: BrowserKind | None) -> set[str]:
    operation_ids_set = set(BROWSER_OPERATION_IDS)
    if kind in {"plugin", "instrument", "effect"}:
        return {item for item in operation_ids_set if item.startswith("plugins.")}
    if kind == "preset":
        return {item for item in operation_ids_set if "preset" in item}
    if kind == "sample":
        return {"channels.load_sample", "audio.analyze"}
    if kind == "drum_kit":
        return {"patterns.create_pattern", "piano-roll.generate_bass", "piano-roll.generate_chords"}
    return operation_ids_set


def _infer_browser_load_operation(
    kind: BrowserKind | None,
    operation_id: str | None,
) -> str:
    if operation_id:
        return operation_id
    if kind in {"plugin", "instrument", "effect", None}:
        return "plugins.load"
    if kind == "preset":
        return "plugins.load_preset_by_name"
    if kind == "sample":
        return "channels.load_sample"
    if kind == "drum_kit":
        return "patterns.create_pattern"
    return "plugins.load"


def _browser_load_request(
    kind: BrowserKind | None,
    query: str | None,
    operation_id: str,
    request: dict[str, object] | None,
) -> dict[str, object]:
    payload = dict(request or {})
    value = query or "FLEX"
    payload.setdefault("channel_index", 0)
    if operation_id == "plugins.load_profile_preset":
        payload.setdefault("profile_id", value)
        if kind == "preset":
            payload.setdefault("preset_name", value)
    elif kind == "preset":
        payload.setdefault("preset_name", value)
    elif kind == "sample":
        payload.setdefault("file_path", value)
    elif kind == "drum_kit":
        payload.pop("channel_index", None)
        payload.setdefault("name", value)
    else:
        payload.setdefault("plugin_name", value)
    return payload


def _redact_local_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        relative = path.relative_to(Path.home())
    except ValueError:
        return f"<local>/{path.name}"
    return f"~/{relative.as_posix()}"


def _redact_inventory_paths(payload: object) -> object:
    if isinstance(payload, list):
        return [_redact_inventory_paths(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    redacted: dict[str, object] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        if key == "path" and isinstance(value, str):
            redacted[key] = _redact_local_path(value)
        elif key in {
            "bundle_paths",
            "fl_database_entries",
            "favorite_entries",
            "preset_paths",
        } and isinstance(value, list):
            redacted[key] = [_redact_local_path(str(item)) for item in value]
        else:
            redacted[key] = _redact_inventory_paths(value)
    return redacted


def _asset_discovery_status(
    kind: BrowserKind | None,
    action: BrowserAction,
    query: str | None = None,
    limit: int = 25,
) -> dict[str, object]:
    status: dict[str, object] = {
        "mode": "capability_workflow_wrapper",
        "action": action,
        "kind": kind,
        "asset_catalog": "plugin_profile_registry",
        "live_load_policy": "fail_closed_unless_provider_supports_exact_operation",
    }
    if kind in {"plugin", "instrument", "effect", "preset"} or query:
        registry = get_plugin_profile_registry()
        bounded_limit = max(1, min(limit, 50))
        profile_hits = registry.search(query, limit=bounded_limit)
        preset_hits = [
            asset.model_dump(mode="json")
            for asset in registry.presets(query, limit=min(bounded_limit, 25))
        ]
        status.update(
            {
                "profile_hits": _redact_inventory_paths(profile_hits),
                "preset_hits": _redact_inventory_paths(preset_hits),
                "asset_discovery_status": "local_inventory_scanned",
                "calibration_policy": "mapped writes require local FL parameter calibration",
            }
        )
    return status


def fl_browser(
    action: BrowserAction = "search",
    query: str | None = None,
    kind: BrowserKind | None = None,
    operation_id: str | None = None,
    request: dict[str, object] | None = None,
    provider: str = "auto",
    limit: int = 25,
) -> dict[str, object]:
    """Search/load plugins, presets, samples, drum kits, and browser-like assets."""

    try:
        ids = _browser_operation_ids(kind)
        if action == "search":
            query_text = query or " ".join(sorted(ids))
            search = fl_search_capabilities(query=query_text, limit=limit)
            results = [
                CapabilitySummaryModel.model_validate(item)
                for item in cast(list[dict[str, object]], search.get("results", []))
                if cast(str, item.get("operation_id")) in ids
                or (query is not None and cast(str, item.get("operation_id")) in ids)
            ]
            if not results:
                results = [
                    _summary_for_spec(_resolve_operation(item))
                    for item in sorted(ids)
                    if item in _OPERATION_BY_ID
                ]
            return FLBrowserResponse(
                status="ok",
                action=action,
                kind=kind,
                query=query,
                results=results[: max(1, min(limit, 100))],
                asset_discovery_status=_asset_discovery_status(kind, action, query, limit),
            ).model_dump(mode="json", exclude_none=True)

        if action == "schema":
            schema_operation = _infer_browser_load_operation(kind, operation_id)
            schema_result = fl_get_capability_schema(schema_operation)
            status = "error" if schema_result.get("status") == "error" else "ok"
            return FLBrowserResponse(
                status=cast(Any, status),
                action=action,
                kind=kind,
                query=query,
                capability_schema=CapabilitySchemaResponse.model_validate(schema_result),
                asset_discovery_status=_asset_discovery_status(kind, action, query, limit),
                error=cast(str | None, schema_result.get("error")),
            ).model_dump(mode="json", exclude_none=True)

        browser_operation = operation_id
        if (
            browser_operation is None
            and request is not None
            and "profile_id" in request
            and kind in {"plugin", "instrument", "effect", "preset", None}
        ):
            browser_operation = "plugins.load_profile_preset"
        load_operation = _infer_browser_load_operation(kind, browser_operation)
        load_request = _browser_load_request(kind, query, load_operation, request)
        load_result = fl_execute(load_operation, load_request, provider=provider)
        status = "error" if load_result.get("status") == "error" else "ok"
        return FLBrowserResponse(
            status=cast(Any, status),
            action=action,
            kind=kind,
            query=query,
            load_result=load_result,
            asset_discovery_status=_asset_discovery_status(kind, action, query, limit),
            error=cast(str | None, load_result.get("error")),
        ).model_dump(mode="json", exclude_none=True)
    except Exception as exc:
        logger.warning("fl_browser failed: %s", exc, exc_info=True)
        return FLBrowserResponse(
            status="error",
            action=action,
            kind=kind,
            query=query,
            asset_discovery_status=_asset_discovery_status(kind, action, query, limit),
            error=str(exc),
        ).model_dump(mode="json", exclude_none=True)
