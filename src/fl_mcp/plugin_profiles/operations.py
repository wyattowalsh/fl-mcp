"""Runtime handlers for declarative plugin-profile operations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast, get_args

from pydantic import BaseModel

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE, BridgeExecutionResult
from fl_mcp.plugin_profiles.inventory import (
    inventory_scan_roots,
    normalize_plugin_id,
    plugin_profile_overlay_dir,
)
from fl_mcp.plugin_profiles.registry import (
    get_plugin_profile_registry,
    normalize_control_value,
)
from fl_mcp.schemas.fl_tools import FLToolRequest
from fl_mcp.schemas.plugin_profiles import (
    PluginCalibration,
    PluginControl,
    PluginFormat,
    PluginInventoryItem,
    PluginPresetAsset,
    PluginProfile,
    PluginProfileFailureCode,
    PluginRawParameter,
    PluginSupportMatrixRow,
    PluginSupportPriority,
    PluginSupportState,
    PluginValueMap,
    PluginWrapperFingerprint,
)
from fl_mcp.util.paths import LocalPathValidationError, is_uri_path, validate_local_path

PROFILE_OPERATIONS: tuple[str, ...] = (
    "inventory_scan",
    "list_profiles",
    "get_profile",
    "resolve_profile",
    "probe_instance",
    "learn_parameter",
    "validate_profile",
    "get_mapped_parameter",
    "set_mapped_parameter",
    "load_profile_preset",
    "list_local_presets",
    "reconcile_inventory",
    "get_parameter_name",
    "enumerate_parameters",
    "probe_loadability",
    "generate_raw_profile",
    "verify_profile_controls",
    "write_calibration_overlay",
    "priority_support_audit",
    "export_support_matrix",
)
PROFILE_OPERATION_IDS: tuple[str, ...] = tuple(
    f"plugins.{operation}" for operation in PROFILE_OPERATIONS
)
PROFILE_OPERATION_SET = set(PROFILE_OPERATIONS)
PROFILE_OPERATION_ID_SET = set(PROFILE_OPERATION_IDS)
PLUGIN_FORMAT_VALUES = set(get_args(PluginFormat))
LOCAL_INVENTORY_STATUSES = {"installed", "filesystem_only", "fl_database_only", "preset_only"}
P0_PROFILE_IDS = {
    "lennardigital.sylenth1",
    "xfer.serum2",
    "xfer.serum2_fx",
    "cableguys.shaperbox2",
    "fabfilter.pro_q3",
    "fabfilter.pro_c2",
}
P1_PROFILE_IDS = {
    "fabfilter.micro",
    "fabfilter.one",
    "fabfilter.twin3",
    "fabfilter.pro_ds",
    "fabfilter.pro_g",
    "fabfilter.pro_l2",
    "fabfilter.pro_mb",
    "fabfilter.pro_r",
    "fabfilter.saturn2",
    "fabfilter.simplon",
    "fabfilter.timeless3",
    "fabfilter.volcano3",
    "d16.drumazon",
    "valhalla.valhallaroom",
    "image_line.fl_studio_vst",
    "izotope.trash",
}
P2_PROFILE_IDS = {
    "camel_audio.camelcrusher",
    "image_line.fruity_parametric_eq_2",
    "image_line.fruity_limiter",
    "image_line.maximus",
    "image_line.gross_beat",
    "image_line.flex",
    "image_line.fpc",
    "image_line.directwave",
    "image_line.edison",
    "image_line.slicex",
    "image_line.sytrus",
    "image_line.harmor",
    "image_line.patcher",
    "image_line.fruity_reeverb_2",
    "image_line.fruity_delay_3",
    "image_line.fruity_soft_clipper",
    "image_line.wave_candy",
}


class _SpecLike(Protocol):
    name: str
    domain: str
    operation: str


def is_plugin_profile_operation(domain: str, operation: str) -> bool:
    """Return whether a domain operation belongs to the plugin-profile subsystem."""

    return domain == "plugins" and operation in PROFILE_OPERATION_SET


def make_plugin_profile_handler(spec: _SpecLike) -> Callable[[FLToolRequest], dict[str, object]]:
    """Build a tool handler compatible with ``FL_TOOL_HANDLERS``."""

    def handler(request: FLToolRequest) -> dict[str, object]:
        return handle_plugin_profile_operation(spec=spec, request=request)

    handler.__name__ = spec.name
    handler.__qualname__ = spec.name
    return handler


def handle_plugin_profile_operation(
    *,
    spec: _SpecLike,
    request: FLToolRequest,
) -> dict[str, object]:
    """Execute one plugin-profile operation."""

    operation = spec.operation
    try:
        if operation == "inventory_scan":
            return _inventory_scan(spec, request)
        if operation == "list_profiles":
            return _list_profiles(spec, request)
        if operation == "get_profile":
            return _get_profile(spec, request)
        if operation == "resolve_profile":
            return _resolve_profile(spec, request)
        if operation == "probe_instance":
            return _probe_instance(spec, request)
        if operation == "learn_parameter":
            return _learn_parameter(spec, request)
        if operation == "validate_profile":
            return _validate_profile(spec, request)
        if operation == "get_mapped_parameter":
            return _get_mapped_parameter(spec, request)
        if operation == "set_mapped_parameter":
            return _set_mapped_parameter(spec, request)
        if operation == "load_profile_preset":
            return _load_profile_preset(spec, request)
        if operation == "list_local_presets":
            return _list_local_presets(spec, request)
        if operation == "reconcile_inventory":
            return _reconcile_inventory(spec, request)
        if operation == "get_parameter_name":
            return _get_parameter_name(spec, request)
        if operation == "enumerate_parameters":
            return _enumerate_parameters(spec, request)
        if operation == "probe_loadability":
            return _probe_loadability(spec, request)
        if operation == "generate_raw_profile":
            return _generate_raw_profile(spec, request)
        if operation == "verify_profile_controls":
            return _verify_profile_controls(spec, request)
        if operation == "write_calibration_overlay":
            return _write_calibration_overlay(spec, request)
        if operation == "priority_support_audit":
            return _priority_support_audit(spec, request)
        if operation == "export_support_matrix":
            return _export_support_matrix(spec, request)
    except ValueError as exc:
        return _response(
            spec,
            request,
            status="error",
            message=str(exc),
            error_code="validation_failed",
            result={"remediation": "Correct the plugin-profile request payload."},
        )
    return _response(
        spec,
        request,
        status="error",
        message=f"Unsupported plugin-profile operation: plugins.{operation}.",
        error_code="unsupported_operation",
        result={"operation_id": f"plugins.{operation}"},
    )


def _request_data(request: FLToolRequest) -> dict[str, object]:
    if isinstance(request, BaseModel):
        return request.model_dump(mode="json", exclude_none=True)
    return dict(cast(dict[str, object], request))


def _int_value(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _plugin_format(value: object) -> PluginFormat:
    if isinstance(value, str) and value in PLUGIN_FORMAT_VALUES:
        return cast(PluginFormat, value)
    return "unknown"


def _bounded_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return None
    else:
        return None
    if 0 <= numeric <= 1:
        return numeric
    return None


def _bridge_result_value(result: BridgeExecutionResult, *keys: str) -> object:
    for key in keys:
        if key in result.result:
            return result.result[key]
    return result.result.get("value")


def _bridge_result_str(result: BridgeExecutionResult, *keys: str) -> str | None:
    value = _bridge_result_value(result, *keys)
    if value is None:
        return None
    return str(value)


def _bridge_result_int(result: BridgeExecutionResult, *keys: str) -> int | None:
    value = _bridge_result_value(result, *keys)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _priority_for(
    item: PluginInventoryItem | None,
    profile: PluginProfile | None,
) -> PluginSupportPriority:
    profile_id = profile.profile_id if profile is not None else None
    item_id = item.plugin_id if item is not None else None
    canonical_ids = {
        normalize_plugin_id(value)
        for value in (profile_id, item_id, item.display_name if item else None)
        if value
    }
    if profile is not None and profile.status == "desired":
        return "desired_not_installed"
    if profile_id in P0_PROFILE_IDS or canonical_ids & P0_PROFILE_IDS:
        return "P0_paid_installed"
    if profile_id in P1_PROFILE_IDS or canonical_ids & P1_PROFILE_IDS:
        if profile_id == "izotope.trash" or "izotope.trash" in canonical_ids:
            return "desired_not_installed"
        return "P1_paid_detected_or_suite"
    if profile_id in P2_PROFILE_IDS or canonical_ids & P2_PROFILE_IDS:
        return "P2_popular_useful_stock_or_free"
    return "P3_inventory_only_on_demand"


def _support_state_for(
    item: PluginInventoryItem | None,
    profile: PluginProfile | None,
    calibration: PluginCalibration | None,
) -> PluginSupportState:
    if profile is not None and profile.status == "desired":
        return "not_installed"
    if item is None or item.status == "not_installed":
        return "not_installed"
    if item.status not in LOCAL_INVENTORY_STATUSES:
        return "inventory_stub"
    if calibration is not None:
        return "calibrated"
    if profile is None:
        return "inventory_stub"
    if profile.raw_parameters:
        return "raw_enumerated"
    if profile.semantic_controls:
        return "semantic_seed"
    return "inventory_stub"


def _support_failure(
    priority: PluginSupportPriority,
    state: PluginSupportState,
    profile: PluginProfile | None,
) -> tuple[str | None, str | None]:
    if priority == "desired_not_installed":
        return "plugin_not_installed", "Install and rescan the plugin before live execution."
    if profile is None and priority != "P3_inventory_only_on_demand":
        return "profile_missing", "Add a priority profile or re-run profile seed generation."
    if state in {"not_installed", "unloadable", "unprobeable", "unsupported_host_behavior"}:
        return "live_probe_failed", "Run plugins.probe_loadability against a scratch project."
    return None, None


def _support_matrix_rows(
    *,
    query: str | None,
    include_p3: bool,
) -> list[PluginSupportMatrixRow]:
    registry = get_plugin_profile_registry()
    rows: list[PluginSupportMatrixRow] = []
    for item in registry.inventory():
        profile = registry.profile(item.plugin_id) or registry.profile(item.display_name)
        priority = _priority_for(item, profile)
        if priority == "P3_inventory_only_on_demand" and not include_p3:
            continue
        if query:
            text = " ".join(
                [
                    item.plugin_id,
                    item.display_name,
                    item.vendor or "",
                    profile.profile_id if profile is not None else "",
                    " ".join(profile.aliases) if profile is not None else "",
                ]
            )
            if query.casefold() not in text.casefold():
                continue
        calibration = registry.calibration_for(profile.profile_id) if profile is not None else None
        state = _support_state_for(item, profile, calibration)
        failure_code, remediation = _support_failure(priority, state, profile)
        rows.append(
            PluginSupportMatrixRow(
                plugin_id=item.plugin_id,
                display_name=item.display_name,
                priority=priority,
                support_state=state,
                inventory_status=item.status,
                profile_id=profile.profile_id if profile is not None else None,
                profile_status=profile.status if profile is not None else None,
                semantic_control_count=len(profile.semantic_controls) if profile else 0,
                raw_parameter_count=len(profile.raw_parameters) if profile else 0,
                formats=list(item.formats),
                detected_by=list(item.detected_by),
                failure_code=cast(PluginProfileFailureCode | None, failure_code),
                remediation=remediation,
            )
        )
    return sorted(rows, key=lambda row: (row.priority, row.display_name.casefold()))


def _parameter_record(
    *,
    parameter_index: int,
    name_result: BridgeExecutionResult | None,
    value_result: BridgeExecutionResult | None,
    value_string_result: BridgeExecutionResult | None,
) -> PluginRawParameter:
    parameter_name = (
        _bridge_result_str(name_result, "parameter_name", "name")
        if name_result is not None and name_result.success
        else None
    )
    normalized = (
        _bounded_float(_bridge_result_value(value_result, "normalized_value", "value"))
        if value_result is not None and value_result.success
        else None
    )
    value_string = (
        _bridge_result_str(value_string_result, "value_string", "text")
        if value_string_result is not None and value_string_result.success
        else None
    )
    risk = "volatile" if parameter_name and _is_volatile_parameter(parameter_name) else "safe"
    return PluginRawParameter(
        parameter_index=parameter_index,
        parameter_name=parameter_name,
        normalized_value=normalized,
        value_string=value_string,
        readable=value_result is None or value_result.success,
        writable=None if risk == "safe" else False,
        write_probe_status="not_run" if risk == "safe" else "skipped",
        risk=risk,
    )


def _is_volatile_parameter(name: str) -> bool:
    normalized = name.casefold()
    return any(
        token in normalized
        for token in ("preset", "program", "random", "reset", "delete", "save", "load")
    )


def _raw_control_id(parameter: PluginRawParameter) -> str:
    if parameter.parameter_name:
        slug = re.sub(r"[^a-z0-9]+", "_", parameter.parameter_name.casefold()).strip("_")
        if slug:
            return f"param.{parameter.parameter_index:04d}.{slug[:48]}"
    return f"param.{parameter.parameter_index:04d}"


def _raw_control_group(parameter: PluginRawParameter) -> str:
    name = (parameter.parameter_name or "").casefold()
    for token, group in (
        ("filter", "filter"),
        ("cutoff", "filter"),
        ("res", "filter"),
        ("osc", "oscillator"),
        ("env", "envelope"),
        ("attack", "envelope"),
        ("release", "envelope"),
        ("lfo", "lfo"),
        ("macro", "macros"),
        ("mix", "mix"),
        ("gain", "output"),
        ("volume", "output"),
        ("output", "output"),
    ):
        if token in name:
            return group
    return "raw"


def _raw_control_value_map(parameter: PluginRawParameter) -> PluginValueMap:
    name = (parameter.parameter_name or "").casefold()
    if any(token in name for token in ("hz", "freq", "cutoff")):
        return PluginValueMap(kind="log_frequency", min_value=20, max_value=20000)
    if any(token in name for token in ("db", "gain")):
        return PluginValueMap(kind="db", min_value=-60, max_value=12)
    if any(token in name for token in ("mix", "amount", "level", "volume")):
        return PluginValueMap(kind="percent")
    return PluginValueMap(kind="normalized")


def _fingerprint_for(
    *,
    plugin_name: str | None,
    plugin_format: PluginFormat,
    parameter_count: int,
    parameters: list[PluginRawParameter],
) -> PluginWrapperFingerprint:
    joined_names = "\n".join(parameter.parameter_name or "" for parameter in parameters)
    return PluginWrapperFingerprint(
        plugin_name=plugin_name,
        format=plugin_format,
        parameter_count=parameter_count,
        parameter_name_hash=hashlib.sha256(joined_names.encode("utf-8")).hexdigest()[:16],
        bridge_mode=DEFAULT_BRIDGE.mode,
    )


def _calibration_file_name(calibration: PluginCalibration) -> str:
    suffix = calibration.fingerprint or calibration.format or "unknown"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{calibration.profile_id}-{suffix}")
    return f"{safe}.json"


def _requested_provider(request: FLToolRequest) -> str:
    value = getattr(request, "provider", "auto")
    return value if isinstance(value, str) and value else "auto"


def _resolved_provider(request: FLToolRequest) -> str:
    requested = _requested_provider(request)
    if requested != "auto":
        return requested
    return "flapi-live" if DEFAULT_BRIDGE.mode == "live" else "mock"


def _response(
    spec: _SpecLike,
    request: FLToolRequest,
    *,
    status: str,
    message: str,
    result: dict[str, object],
    error_code: str | None = None,
    execution_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "provider": _resolved_provider(request),
        "bridge_mode": DEFAULT_BRIDGE.mode,
        "execution_id": execution_id,
        "message": message,
        "result": result,
        "error_code": error_code,
    }
    if status == "error":
        payload["error"] = message
    return {key: value for key, value in payload.items() if value is not None}


def _bridge_response(
    spec: _SpecLike,
    request: FLToolRequest,
    bridge_result: BridgeExecutionResult,
    *,
    result: dict[str, object] | None = None,
) -> dict[str, object]:
    merged = dict(bridge_result.result)
    if result:
        merged.update(result)
    status = "ok" if bridge_result.success else "error"
    payload: dict[str, object] = {
        "status": status,
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "provider": bridge_result.provider,
        "bridge_mode": bridge_result.bridge_mode,
        "execution_id": bridge_result.execution_id,
        "message": bridge_result.message,
        "result": merged,
        "error_code": bridge_result.error_code,
    }
    if not bridge_result.success:
        payload["error"] = bridge_result.message
    return {key: value for key, value in payload.items() if value is not None}


def _redact_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        home = Path.home()
        relative = path.relative_to(home)
    except ValueError:
        return f"<local>/{path.name}"
    return f"~/{relative.as_posix()}"


def _inventory_payload(item: PluginInventoryItem, *, include_paths: bool) -> dict[str, object]:
    payload = item.model_dump(mode="json")
    if not include_paths:
        for key in ("bundle_paths", "fl_database_entries", "favorite_entries", "preset_paths"):
            values = payload.get(key)
            if isinstance(values, list):
                payload[key] = [_redact_path(str(value)) for value in values]
    return payload


def _preset_payload(asset: PluginPresetAsset, *, include_paths: bool) -> dict[str, object]:
    payload = asset.model_dump(mode="json")
    if not include_paths:
        payload["path"] = _redact_path(asset.path)
    return payload


def _profile_payload(
    profile: PluginProfile,
    *,
    inventory: PluginInventoryItem | None = None,
    calibration: PluginCalibration | None = None,
    include_paths: bool = False,
) -> dict[str, object]:
    return {
        "profile": profile.model_dump(mode="json"),
        "inventory": _inventory_payload(inventory, include_paths=include_paths)
        if inventory is not None
        else None,
        "calibration": calibration.model_dump(mode="json") if calibration is not None else None,
        "calibration_status": "available" if calibration is not None else "required",
    }


def _profile_or_error(
    spec: _SpecLike,
    request: FLToolRequest,
    profile_id: str | None,
) -> tuple[PluginProfile | None, dict[str, object] | None]:
    if not profile_id:
        return None, _response(
            spec,
            request,
            status="error",
            message="profile_id is required.",
            error_code="profile_missing",
            result={"remediation": "Provide a plugin profile_id such as lennardigital.sylenth1."},
        )
    registry = get_plugin_profile_registry()
    profile = registry.profile(profile_id)
    if profile is None:
        return None, _response(
            spec,
            request,
            status="error",
            message=f"Plugin profile is not registered: {profile_id}.",
            error_code="profile_missing",
            result={"profile_id": profile_id, "remediation": "Run plugins.resolve_profile first."},
        )
    return profile, None


def _inventory_scan(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    if bool(data.get("rescan", False)):
        registry.clear_caches()
    query = cast(str | None, data.get("query"))
    include_paths = bool(data.get("include_paths", False))
    include_presets = bool(data.get("include_presets", True))
    limit = _int_value(data.get("limit"), 100)
    matches = registry.search(query, limit=limit)
    inventory = [
        _inventory_payload(item, include_paths=include_paths)
        for item in registry.inventory()
        if not query
        or query.casefold() in item.display_name.casefold()
        or query.casefold() in item.plugin_id.casefold()
    ][:limit]
    presets = (
        [
            _preset_payload(asset, include_paths=include_paths)
            for asset in registry.presets(query, limit=limit)
        ]
        if include_presets
        else []
    )
    return _response(
        spec,
        request,
        status="ok",
        message="Plugin inventory scan completed.",
        result={
            "inventory": inventory,
            "profile_inventory_matches": matches,
            "presets": presets,
            "counts": {
                "inventory": len(inventory),
                "presets": len(presets),
                "profiles": len(registry.profiles()),
            },
        },
    )


def _list_profiles(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    query = cast(str | None, data.get("query"))
    status_filter = cast(str | None, data.get("status"))
    include_inventory = bool(data.get("include_inventory", True))
    limit = _int_value(data.get("limit"), 100)
    rows: list[dict[str, object]] = []
    for profile in registry.profiles():
        if status_filter and profile.status != status_filter:
            continue
        text = " ".join([profile.profile_id, profile.display_name, " ".join(profile.aliases)])
        if query and query.casefold() not in text.casefold():
            continue
        inventory = registry.inventory_item(profile.profile_id) if include_inventory else None
        rows.append(_profile_payload(profile, inventory=inventory))
    return _response(
        spec,
        request,
        status="ok",
        message="Plugin profiles listed.",
        result={"profiles": rows[:limit], "count": min(len(rows), limit), "total": len(rows)},
    )


def _get_profile(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    registry = get_plugin_profile_registry()
    inventory = (
        registry.inventory_item(profile.profile_id) if data.get("include_inventory", True) else None
    )
    calibration = (
        registry.calibration_for(profile.profile_id)
        if data.get("include_calibration", True)
        else None
    )
    return _response(
        spec,
        request,
        status="ok",
        message=f"Plugin profile resolved: {profile.display_name}.",
        result=_profile_payload(profile, inventory=inventory, calibration=calibration),
    )


def _resolve_profile(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    query = str(data.get("query", "")).strip()
    results = registry.search(query, limit=_int_value(data.get("limit"), 25))
    return _response(
        spec,
        request,
        status="ok",
        message=f"Resolved {len(results)} plugin profile/inventory candidates.",
        result={"query": query, "matches": results},
    )


def _target_payload(
    request: FLToolRequest, *, parameter_index: int | None = None
) -> dict[str, object]:
    data = _request_data(request)
    channel_index = _int_value(data.get("channel_index"), 0)
    plugin_slot = data.get("plugin_slot")
    payload: dict[str, object] = {
        "channel_index": channel_index,
        "index": channel_index,
    }
    if isinstance(plugin_slot, int):
        payload["plugin_slot"] = plugin_slot
        payload["slot_index"] = plugin_slot
    if parameter_index is not None:
        payload.update(
            {
                "parameter": str(parameter_index),
                "parameter_index": parameter_index,
                "param_index": parameter_index,
            }
        )
    return payload


def _probe_instance(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    probe_payload = _target_payload(request)
    calls: dict[str, dict[str, object]] = {}
    for operation in ("is_valid", "get_name", "get_parameter_count"):
        result = DEFAULT_BRIDGE.execute_operation(
            domain="plugins",
            operation=operation,
            payload=probe_payload,
            provider=_requested_provider(request),
        )
        calls[operation] = _bridge_call_payload(result)
    success = all(item.get("success") is True for item in calls.values())
    status = "ok" if success else "error"
    message = (
        "Plugin instance probe completed." if success else "Plugin instance live probe failed."
    )
    return _response(
        spec,
        request,
        status=status,
        message=message,
        error_code=None if success else "live_probe_failed",
        result={"probe": calls, "target": probe_payload},
    )


def _get_parameter_name(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    parameter_index = _int_value(data.get("parameter_index"), 0)
    bridge_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="get_parameter_name",
        payload=_target_payload(request, parameter_index=parameter_index),
        provider=_requested_provider(request),
    )
    return _bridge_response(
        spec,
        request,
        bridge_result,
        result={"parameter_index": parameter_index},
    )


def _enumerate_parameter_records(
    request: FLToolRequest,
) -> tuple[dict[str, object], list[PluginRawParameter], list[dict[str, object]]]:
    data = _request_data(request)
    cursor = _int_value(data.get("cursor"), 0)
    max_parameters = max(1, min(_int_value(data.get("max_parameters"), 256), 4096))
    include_values = bool(data.get("include_values", True))
    include_value_strings = bool(data.get("include_value_strings", True))
    target = _target_payload(request)
    provider = _requested_provider(request)
    calls: dict[str, dict[str, object]] = {}

    is_valid = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="is_valid",
        payload=target,
        provider=provider,
    )
    calls["is_valid"] = _bridge_call_payload(is_valid)
    if not is_valid.success:
        return (
            {
                "target": target,
                "probe": calls,
                "parameter_count": 0,
                "cursor": cursor,
                "next_cursor": None,
                "partial": False,
            },
            [],
            [],
        )

    name_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="get_name",
        payload=target,
        provider=provider,
    )
    count_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="get_parameter_count",
        payload=target,
        provider=provider,
    )
    calls["get_name"] = _bridge_call_payload(name_result)
    calls["get_parameter_count"] = _bridge_call_payload(count_result)
    count_failure: dict[str, object] | None = None
    if not count_result.success:
        count_failure = {
            "operation": "get_parameter_count",
            "error_code": count_result.error_code,
            "message": count_result.message,
        }
    parameter_count = _bridge_result_int(count_result, "parameter_count", "count") or 0
    end = min(parameter_count, cursor + max_parameters)
    parameters: list[PluginRawParameter] = []
    failures: list[dict[str, object]] = []
    for parameter_index in range(cursor, end):
        payload = _target_payload(request, parameter_index=parameter_index)
        name_probe = DEFAULT_BRIDGE.execute_operation(
            domain="plugins",
            operation="get_parameter_name",
            payload=payload,
            provider=provider,
        )
        value_probe = (
            DEFAULT_BRIDGE.execute_operation(
                domain="plugins",
                operation="get_parameter",
                payload=payload,
                provider=provider,
            )
            if include_values
            else None
        )
        value_string_probe = (
            DEFAULT_BRIDGE.execute_operation(
                domain="plugins",
                operation="get_param_value_string",
                payload=payload,
                provider=provider,
            )
            if include_value_strings
            else None
        )
        for probe_name, probe in (
            ("get_parameter_name", name_probe),
            ("get_parameter", value_probe),
            ("get_param_value_string", value_string_probe),
        ):
            if probe is not None and not probe.success:
                failures.append(
                    {
                        "parameter_index": parameter_index,
                        "operation": probe_name,
                        "error_code": probe.error_code,
                        "message": probe.message,
                    }
                )
        parameters.append(
            _parameter_record(
                parameter_index=parameter_index,
                name_result=name_probe,
                value_result=value_probe,
                value_string_result=value_string_probe,
            )
        )
    next_cursor = end if end < parameter_count else None
    if count_failure is not None:
        failures.append(count_failure)
    payload: dict[str, object] = {
        "target": target,
        "plugin_name": _bridge_result_str(name_result, "name", "plugin_name"),
        "parameter_count": parameter_count,
        "cursor": cursor,
        "next_cursor": next_cursor,
        "partial": next_cursor is not None or bool(failures),
        "probe_failed": count_failure is not None,
        "probe": calls,
        "failures": failures,
    }
    return payload, parameters, failures


def _enumerate_parameters(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    payload, parameters, failures = _enumerate_parameter_records(request)
    status = "ok"
    error_code = None
    message = "Plugin parameter enumeration completed."
    if payload.get("probe_failed") is True:
        status = "error"
        error_code = "live_probe_failed"
        message = "Plugin parameter enumeration failed during live probe."
    elif payload.get("parameter_count") == 0 and not parameters:
        is_valid = cast(dict[str, object], payload.get("probe", {})).get("is_valid")
        if isinstance(is_valid, dict) and is_valid.get("success") is not True:
            status = "error"
            error_code = "live_probe_failed"
            message = "Plugin parameter enumeration failed during live probe."
    return _response(
        spec,
        request,
        status=status,
        message=message,
        error_code=error_code,
        result={
            **payload,
            "parameters": [parameter.model_dump(mode="json") for parameter in parameters],
            "failure_count": len(failures),
        },
    )


def _probe_loadability(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    profile_id = cast(str | None, data.get("profile_id"))
    profile = registry.profile(profile_id) if profile_id else None
    inventory = registry.inventory_item(profile.profile_id if profile else profile_id or "")
    _, parameters, failures = _enumerate_parameter_records(request)
    loadable = bool(parameters) or not failures
    state = "loadable" if loadable else "unprobeable"
    return _response(
        spec,
        request,
        status="ok" if loadable else "error",
        message="Plugin loadability probe completed." if loadable else "Plugin probe failed.",
        error_code=None if loadable else "live_probe_failed",
        result={
            "profile": profile.model_dump(mode="json") if profile else None,
            "inventory": _inventory_payload(inventory, include_paths=False)
            if inventory is not None
            else None,
            "support_state": state,
            "parameter_count": len(parameters),
            "failures": failures,
        },
    )


def _generate_raw_profile(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    requested_profile_id = cast(str | None, data.get("profile_id"))
    profile = registry.profile(requested_profile_id) if requested_profile_id else None
    payload, parameters, failures = _enumerate_parameter_records(request)
    plugin_name = cast(str | None, payload.get("plugin_name")) or (
        profile.display_name if profile is not None else "Plugin"
    )
    profile_id = (
        profile.profile_id
        if profile is not None
        else normalize_plugin_id(requested_profile_id or plugin_name)
    )
    controls = [
        PluginControl(
            control_id=_raw_control_id(parameter),
            label=parameter.parameter_name or f"Parameter {parameter.parameter_index}",
            group=_raw_control_group(parameter),
            value_map=_raw_control_value_map(parameter),
            parameter_index=parameter.parameter_index,
            parameter_name_hint=parameter.parameter_name,
            control_origin="live_raw",
            readback=parameter.readable,
            risk=parameter.risk,
        )
        for parameter in parameters
    ]
    fingerprint = _fingerprint_for(
        plugin_name=plugin_name,
        plugin_format=_plugin_format(data.get("plugin_format")),
        parameter_count=cast(int, payload.get("parameter_count") or len(parameters)),
        parameters=parameters,
    )
    raw_profile = PluginProfile(
        profile_id=profile_id,
        vendor=profile.vendor if profile else None,
        family=profile.family if profile else plugin_name,
        display_name=profile.display_name if profile else plugin_name,
        aliases=list(profile.aliases) if profile else [plugin_name],
        kind=profile.kind if profile else "unknown",
        supported_formats=list(profile.supported_formats) if profile else [],
        semantic_controls=controls,
        support_priority=_priority_for(None, profile),
        support_state="raw_enumerated" if parameters else "unprobeable",
        raw_parameters=parameters,
        wrapper_fingerprint=fingerprint,
        coverage_evidence={
            "generated_from": "plugins.enumerate_parameters",
            "failure_count": len(failures),
            "bridge_mode": DEFAULT_BRIDGE.mode,
        },
        provenance=list(profile.provenance) if profile else [],
        confidence=profile.confidence if profile else 0.25,
        status="partial" if parameters else "stub",
    )
    return _response(
        spec,
        request,
        status="ok" if parameters else "error",
        message="Raw plugin profile generated." if parameters else "Raw profile generation failed.",
        error_code=None if parameters else "live_probe_failed",
        result={
            "raw_profile": raw_profile.model_dump(mode="json"),
            "fingerprint": fingerprint.model_dump(mode="json"),
            "failure_count": len(failures),
            "persistence": "not_written",
        },
    )


def _bridge_call_payload(result: BridgeExecutionResult) -> dict[str, object]:
    return {
        "success": result.success,
        "provider": result.provider,
        "bridge_mode": result.bridge_mode,
        "execution_id": result.execution_id,
        "message": result.message,
        "error_code": result.error_code,
        "result": result.result,
    }


def _learn_parameter(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    control_id = str(data.get("control_id", ""))
    control = next(
        (item for item in profile.semantic_controls if item.control_id == control_id), None
    )
    if control is None:
        return _response(
            spec,
            request,
            status="error",
            message=f"Control {control_id} is not mapped in profile {profile.profile_id}.",
            error_code="parameter_unmapped",
            result={"profile_id": profile.profile_id, "control_id": control_id},
        )
    observed = data.get("observed_parameter_index")
    if not isinstance(observed, int):
        return _response(
            spec,
            request,
            status="error",
            message="Interactive calibration needs observed_parameter_index from a live probe.",
            error_code="calibration_required",
            result={
                "profile_id": profile.profile_id,
                "control_id": control.control_id,
                "remediation": (
                    "Probe the plugin in FL, move the control, then call "
                    "plugins.learn_parameter with the changed parameter index."
                ),
            },
        )
    calibration = PluginCalibration(
        profile_id=profile.profile_id,
        format=_plugin_format(data.get("plugin_format")),
        mapped_controls={control.control_id: observed},
        bridge_mode=DEFAULT_BRIDGE.mode,
        source="transient",
        fingerprint=cast(str | None, data.get("fingerprint")),
    )
    return _response(
        spec,
        request,
        status="ok",
        message="Transient plugin parameter mapping learned.",
        result={
            "profile_id": profile.profile_id,
            "control_id": control.control_id,
            "calibration": calibration.model_dump(mode="json"),
            "persistence": "not_written",
        },
    )


def _validate_profile(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    registry = get_plugin_profile_registry()
    inventory = registry.inventory_item(profile.profile_id)
    calibration = registry.calibration_for(
        profile.profile_id,
        plugin_format=cast(str | None, data.get("plugin_format")),
        fingerprint=cast(str | None, data.get("fingerprint")),
    )
    unmapped_controls = [
        control.control_id
        for control in profile.semantic_controls
        if control.parameter_index is None
        and (calibration is None or control.control_id not in calibration.mapped_controls)
    ]
    ready = bool(inventory and inventory.status == "installed" and not unmapped_controls)
    return _response(
        spec,
        request,
        status="ok",
        message="Plugin profile validation completed.",
        result={
            "profile": profile.model_dump(mode="json"),
            "inventory": _inventory_payload(inventory, include_paths=False)
            if inventory is not None
            else None,
            "calibration": calibration.model_dump(mode="json") if calibration else None,
            "ready_for_mapped_execution": ready,
            "unmapped_controls": unmapped_controls,
            "failure_code": None if ready else "calibration_required",
        },
    )


def _resolve_mapped_control(
    spec: _SpecLike,
    request: FLToolRequest,
) -> tuple[PluginProfile | None, PluginControl | None, int | None, dict[str, object] | None]:
    data = _request_data(request)
    profile, control, parameter_index, calibration = get_plugin_profile_registry().resolve_control(
        str(data.get("profile_id", "")),
        str(data.get("control_id", "")),
        plugin_format=cast(str | None, data.get("plugin_format")),
        fingerprint=cast(str | None, data.get("fingerprint")),
    )
    if profile is None:
        return (
            None,
            None,
            None,
            _response(
                spec,
                request,
                status="error",
                message=f"Plugin profile is not registered: {data.get('profile_id')}.",
                error_code="profile_missing",
                result={"remediation": "Run plugins.resolve_profile before mapped execution."},
            ),
        )
    if control is None:
        return (
            profile,
            None,
            None,
            _response(
                spec,
                request,
                status="error",
                message=f"Control {data.get('control_id')} is not mapped in {profile.profile_id}.",
                error_code="parameter_unmapped",
                result={"profile_id": profile.profile_id, "control_id": data.get("control_id")},
            ),
        )
    if control.requires_midi:
        return (
            profile,
            control,
            None,
            _response(
                spec,
                request,
                status="error",
                message=f"Control {control.control_id} requires MIDI routing before execution.",
                error_code="midi_routing_required",
                result={"profile_id": profile.profile_id, "control_id": control.control_id},
            ),
        )
    if parameter_index is None:
        return (
            profile,
            control,
            None,
            _response(
                spec,
                request,
                status="error",
                message=f"Control {control.control_id} requires local FL parameter calibration.",
                error_code="calibration_required",
                result={
                    "profile_id": profile.profile_id,
                    "control_id": control.control_id,
                    "calibration": calibration.model_dump(mode="json") if calibration else None,
                    "remediation": "Run plugins.probe_instance then plugins.learn_parameter.",
                },
            ),
        )
    return profile, control, parameter_index, None


def _get_mapped_parameter(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    profile, control, parameter_index, error = _resolve_mapped_control(spec, request)
    if error is not None:
        return error
    assert profile is not None
    assert control is not None
    assert parameter_index is not None
    bridge_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="get_parameter",
        payload=_target_payload(request, parameter_index=parameter_index),
        provider=_requested_provider(request),
    )
    return _bridge_response(
        spec,
        request,
        bridge_result,
        result={
            "profile_id": profile.profile_id,
            "control_id": control.control_id,
            "parameter_index": parameter_index,
        },
    )


def _set_mapped_parameter(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    profile, control, parameter_index, error = _resolve_mapped_control(spec, request)
    if error is not None:
        return error
    assert profile is not None
    assert control is not None
    assert parameter_index is not None
    data = _request_data(request)
    normalized = normalize_control_value(control, cast(float | int | str, data["value"]))
    payload = _target_payload(request, parameter_index=parameter_index)
    payload["value"] = normalized
    bridge_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="set_parameter",
        payload=payload,
        provider=_requested_provider(request),
    )
    if not bridge_result.success:
        return _bridge_response(
            spec,
            request,
            bridge_result,
            result={
                "profile_id": profile.profile_id,
                "control_id": control.control_id,
                "parameter_index": parameter_index,
                "normalized_value": normalized,
            },
        )
    readback_result: dict[str, object] | None = None
    if control.readback:
        readback = DEFAULT_BRIDGE.execute_operation(
            domain="plugins",
            operation="get_parameter",
            payload=_target_payload(request, parameter_index=parameter_index),
            provider=_requested_provider(request),
        )
        readback_result = _bridge_call_payload(readback)
        if not readback.success:
            return _response(
                spec,
                request,
                status="error",
                message="Plugin mapped parameter readback failed after set.",
                error_code="readback_mismatch",
                execution_id=bridge_result.execution_id,
                result={
                    "set": _bridge_call_payload(bridge_result),
                    "readback": readback_result,
                    "profile_id": profile.profile_id,
                    "control_id": control.control_id,
                    "parameter_index": parameter_index,
                    "normalized_value": normalized,
                },
            )
    return _bridge_response(
        spec,
        request,
        bridge_result,
        result={
            "profile_id": profile.profile_id,
            "control_id": control.control_id,
            "parameter_index": parameter_index,
            "normalized_value": normalized,
            "readback": readback_result,
        },
    )


def _load_profile_preset(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    inventory = get_plugin_profile_registry().inventory_item(profile.profile_id)
    if inventory is None or inventory.status == "not_installed":
        return _response(
            spec,
            request,
            status="error",
            message=f"Plugin is not installed or not visible to FL: {profile.display_name}.",
            error_code="plugin_not_installed",
            result={
                "profile_id": profile.profile_id,
                "inventory": None
                if inventory is None
                else _inventory_payload(inventory, include_paths=False),
            },
        )
    preset_path = cast(str | None, data.get("preset_path"))
    preset_name = cast(str | None, data.get("preset_name"))
    if preset_path:
        if is_uri_path(preset_path):
            return _response(
                spec,
                request,
                status="error",
                message="Preset path must be a local file under inventory roots.",
                error_code="validation_failed",
                result={"preset_path": preset_path},
            )
        try:
            path = validate_local_path(
                preset_path,
                allowed_roots=inventory_scan_roots(),
                must_exist=True,
                allow_uri=False,
            )
        except LocalPathValidationError as exc:
            return _response(
                spec,
                request,
                status="error",
                message=str(exc),
                error_code="validation_failed",
                result={"preset_path": _redact_path(preset_path)},
            )
        resolved_path = Path(path) if isinstance(path, str) else path
        if not resolved_path.is_file():
            return _response(
                spec,
                request,
                status="error",
                message=f"Preset path is unavailable: {_redact_path(str(path))}.",
                error_code="preset_unavailable",
                result={"preset_path": _redact_path(str(resolved_path))},
            )
        preset_name = resolved_path.stem
    if not preset_name:
        return _response(
            spec,
            request,
            status="error",
            message="preset_name or preset_path is required for profile preset loading.",
            error_code="preset_unavailable",
            result={"profile_id": profile.profile_id},
        )
    payload = _target_payload(request)
    payload["preset_name"] = preset_name
    bridge_result = DEFAULT_BRIDGE.execute_operation(
        domain="plugins",
        operation="load_preset_by_name",
        payload=payload,
        provider=_requested_provider(request),
    )
    return _bridge_response(
        spec,
        request,
        bridge_result,
        result={"profile_id": profile.profile_id, "preset_name": preset_name},
    )


def _list_local_presets(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    query = cast(str | None, data.get("query") or data.get("profile_id"))
    include_paths = bool(data.get("include_paths", False))
    limit = _int_value(data.get("limit"), 100)
    presets = [
        _preset_payload(asset, include_paths=include_paths)
        for asset in registry.presets(query, limit=limit)
    ]
    return _response(
        spec,
        request,
        status="ok",
        message="Local plugin presets listed.",
        result={"presets": presets, "count": len(presets)},
    )


def _reconcile_inventory(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    query = cast(str | None, data.get("query"))
    include_paths = bool(data.get("include_paths", False))
    rows = [
        item
        for item in registry.inventory()
        if not query
        or query.casefold() in item.display_name.casefold()
        or query.casefold() in item.plugin_id.casefold()
    ]
    by_status: dict[str, list[dict[str, object]]] = {}
    for item in rows:
        by_status.setdefault(item.status, []).append(
            _inventory_payload(item, include_paths=include_paths)
        )
    return _response(
        spec,
        request,
        status="ok",
        message="Plugin inventory reconciliation completed.",
        result={
            "by_status": by_status,
            "counts": {status: len(items) for status, items in sorted(by_status.items())},
        },
    )


def _verify_profile_controls(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    registry = get_plugin_profile_registry()
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    calibration = registry.calibration_for(
        profile.profile_id,
        plugin_format=cast(str | None, data.get("plugin_format")),
        fingerprint=cast(str | None, data.get("fingerprint")),
    )
    if calibration is None:
        return _response(
            spec,
            request,
            status="error",
            message=f"Profile {profile.profile_id} has no verified local calibration.",
            error_code="calibration_required",
            result={
                "profile_id": profile.profile_id,
                "remediation": "Run plugins.learn_parameter or plugins.write_calibration_overlay.",
            },
        )
    verified: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for control_id, parameter_index in calibration.mapped_controls.items():
        result = DEFAULT_BRIDGE.execute_operation(
            domain="plugins",
            operation="get_parameter",
            payload=_target_payload(request, parameter_index=parameter_index),
            provider=_requested_provider(request),
        )
        row: dict[str, object] = {
            "control_id": control_id,
            "parameter_index": parameter_index,
            "readback": _bridge_call_payload(result),
        }
        if result.success:
            verified.append(row)
        else:
            failures.append(row)
    return _response(
        spec,
        request,
        status="ok" if not failures else "error",
        message=(
            "Profile controls verified." if not failures else "Profile control verification failed."
        ),
        error_code=None if not failures else "readback_mismatch",
        result={
            "profile_id": profile.profile_id,
            "calibration": calibration.model_dump(mode="json"),
            "verified_controls": verified,
            "failures": failures,
        },
    )


def _write_calibration_overlay(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    profile, error = _profile_or_error(spec, request, cast(str | None, data.get("profile_id")))
    if error is not None:
        return error
    assert profile is not None
    mapped_controls = cast(dict[str, int], data.get("mapped_controls") or {})
    if not mapped_controls:
        return _response(
            spec,
            request,
            status="error",
            message="mapped_controls is required to write a calibration overlay.",
            error_code="calibration_required",
            result={"profile_id": profile.profile_id},
        )
    calibration = PluginCalibration(
        profile_id=profile.profile_id,
        format=_plugin_format(data.get("plugin_format")),
        fl_reported_name=cast(str | None, data.get("fl_reported_name")),
        parameter_count=cast(int | None, data.get("parameter_count")),
        mapped_controls=mapped_controls,
        verified_at=datetime.now(UTC).isoformat(),
        bridge_mode=DEFAULT_BRIDGE.mode,
        source="local_overlay",
        fingerprint=cast(str | None, data.get("fingerprint")),
    )
    if not bool(data.get("persist", True)):
        return _response(
            spec,
            request,
            status="ok",
            message="Calibration overlay validated in memory.",
            result={
                "profile_id": profile.profile_id,
                "calibration": calibration.model_dump(mode="json"),
                "persistence": "not_written",
            },
        )
    get_plugin_profile_registry().upsert_calibration(calibration)
    directory = plugin_profile_overlay_dir() / "calibrations"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / _calibration_file_name(calibration)
    if target.is_symlink():
        return _response(
            spec,
            request,
            status="error",
            message="Refusing to write calibration overlay through a symlink.",
            error_code="path_unavailable",
            result={"path": _redact_path(str(target))},
        )
    payload = calibration.model_dump(mode="json")
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)
    return _response(
        spec,
        request,
        status="ok",
        message="Calibration overlay written.",
        result={
            "profile_id": profile.profile_id,
            "calibration": payload,
            "persistence": "written",
            "path": _redact_path(str(target)),
        },
    )


def _priority_support_audit(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    include_p3 = bool(data.get("include_p3", True))
    rows = _support_matrix_rows(
        query=cast(str | None, data.get("query")),
        include_p3=include_p3,
    )
    counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    blockers: list[dict[str, object]] = []
    for row in rows:
        counts[row.priority] = counts.get(row.priority, 0) + 1
        state_counts[row.support_state] = state_counts.get(row.support_state, 0) + 1
        if row.priority in {
            "P0_paid_installed",
            "P1_paid_detected_or_suite",
            "P2_popular_useful_stock_or_free",
        } and (row.profile_id is None or row.failure_code is not None):
            blockers.append(row.model_dump(mode="json"))
    fail_on_missing = bool(data.get("fail_on_missing_priority", True))
    status = "error" if fail_on_missing and blockers else "ok"
    return _response(
        spec,
        request,
        status=status,
        message="Priority plugin support audit completed.",
        error_code="profile_missing" if status == "error" else None,
        result={
            "counts_by_priority": dict(sorted(counts.items())),
            "counts_by_support_state": dict(sorted(state_counts.items())),
            "blocking_count": len(blockers),
            "blockers": blockers,
            "rows": [row.model_dump(mode="json") for row in rows],
        },
    )


def _export_support_matrix(spec: _SpecLike, request: FLToolRequest) -> dict[str, object]:
    data = _request_data(request)
    rows = _support_matrix_rows(
        query=cast(str | None, data.get("query")),
        include_p3=bool(data.get("include_p3", True)),
    )
    return _response(
        spec,
        request,
        status="ok",
        message="Plugin support matrix exported.",
        result={
            "rows": [row.model_dump(mode="json") for row in rows],
            "count": len(rows),
            "policy": (
                "P0/P1/P2 are curated priority targets; P3 remains inventory-visible on demand."
            ),
        },
    )
