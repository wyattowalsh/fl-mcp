"""Typed contracts for the compact FastMCP agent surface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SurfaceStatus = Literal["ok", "partial", "error"]
BatchPolicy = Literal["stop-on-error", "continue-on-error"]
ReadbackPolicy = Literal["none", "after_each", "after_batch"]
BrowserAction = Literal["search", "schema", "load"]
BrowserKind = Literal["plugin", "preset", "sample", "drum_kit", "instrument", "effect", "asset"]
ProviderSupportStatus = Literal[
    "available",
    "attemptable",
    "requires_setup",
    "mock_only",
    "unsupported",
]
ProviderSupportMode = Literal["mock", "host_file_bridge", "selected_controller", "custom_provider"]


class ProviderSupportModel(BaseModel):
    provider: str
    status: ProviderSupportStatus
    mode: ProviderSupportMode
    preconditions: list[str] = Field(default_factory=list)
    readback_operation_id: str | None = None
    failure_policy: str = "fail_closed"


class CapabilitySafetyModel(BaseModel):
    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    open_world: bool = True
    rollback_class: str | None = None
    readback_guidance: str | None = None


class CapabilitySummaryModel(BaseModel):
    operation_id: str
    tool_name: str
    domain: str
    operation: str
    description: str
    tags: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    provider_support_details: list[ProviderSupportModel] = Field(default_factory=list)
    default_provider: str | None = None
    execution_mode: str
    request_model: str
    response_model: str
    task: bool = False
    timeout: float | None = None
    safety: CapabilitySafetyModel = Field(default_factory=CapabilitySafetyModel)
    example_request: dict[str, object] = Field(default_factory=dict)


class CapabilitySearchResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_search_capabilities"] = "fl_search_capabilities"
    total: int
    count: int
    query: str | None = None
    filters: dict[str, object] = Field(default_factory=dict)
    results: list[CapabilitySummaryModel] = Field(default_factory=list)
    error: str | None = None


class CapabilitySchemaResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_get_capability_schema"] = "fl_get_capability_schema"
    operation_id: str
    capability: CapabilitySummaryModel | None = None
    request_schema: dict[str, object] = Field(default_factory=dict)
    response_schema: dict[str, object] = Field(default_factory=dict)
    examples: list[dict[str, object]] = Field(default_factory=list)
    provider_support: list[str] = Field(default_factory=list)
    provider_support_details: list[ProviderSupportModel] = Field(default_factory=list)
    error: str | None = None


class CapabilityReadbackRequest(BaseModel):
    operation_id: str
    request: dict[str, object] = Field(default_factory=dict)
    provider: str = "auto"


class FLExecuteResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_execute"] = "fl_execute"
    operation_id: str
    provider: str | None = None
    bridge_mode: str | None = None
    execution_id: str | None = None
    task_id: str | None = None
    operation: CapabilitySummaryModel | None = None
    result: dict[str, object] = Field(default_factory=dict)
    readback: dict[str, object] | None = None
    error: str | None = None


class FLBatchOperationRequest(BaseModel):
    operation_id: str
    request: dict[str, object] = Field(default_factory=dict)
    provider: str = "auto"
    readback: CapabilityReadbackRequest | None = None
    label: str | None = None


class FLBatchExecuteResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_batch_execute"] = "fl_batch_execute"
    policy: BatchPolicy
    readback_policy: ReadbackPolicy
    total: int
    succeeded: int
    failed: int
    results: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None


class FLStatusResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_status"] = "fl_status"
    runtime: dict[str, object] = Field(default_factory=dict)
    connection: dict[str, object] = Field(default_factory=dict)
    capabilities: dict[str, object] = Field(default_factory=dict)
    providers: list[dict[str, object]] = Field(default_factory=list)
    bridge: dict[str, object] = Field(default_factory=dict)
    tasks: dict[str, object] = Field(default_factory=dict)


class FLSnapshotResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_snapshot"] = "fl_snapshot"
    domain: str
    data: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class FLPlanResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_plan"] = "fl_plan"
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class FLApplyResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_apply"] = "fl_apply"
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class FLTaskEntryResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_render", "fl_analyze_audio"]
    result: dict[str, object] = Field(default_factory=dict)
    task_id: str | None = None
    error: str | None = None


class FLProviderManagementResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_manage_providers"] = "fl_manage_providers"
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class FLBrowserResponse(BaseModel):
    status: SurfaceStatus
    tool: Literal["fl_browser"] = "fl_browser"
    action: BrowserAction
    kind: BrowserKind | None = None
    query: str | None = None
    results: list[CapabilitySummaryModel] = Field(default_factory=list)
    capability_schema: CapabilitySchemaResponse | None = None
    load_result: dict[str, object] | None = None
    asset_discovery_status: dict[str, object] | None = None
    error: str | None = None
