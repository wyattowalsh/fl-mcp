"""Typed runtime/public surface schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.schemas._types import TaskState


class RuntimeToolDescriptorModel(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuntimeResourceDescriptorModel(BaseModel):
    uri: str
    name: str | None = None
    description: str | None = None
    mime_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuntimePromptDescriptorModel(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuntimeCapabilityCounts(BaseModel):
    tool_count: int = 0
    resource_count: int = 0
    prompt_count: int = 0
    fl_tool_count: int = 0


class InspectRuntimeResponse(BaseModel):
    status: Literal["ok"] = "ok"
    tool: Literal["inspect_runtime"] = "inspect_runtime"
    transport: str = "unknown"
    fastmcp_runtime: bool | None = None
    auth_required: bool = False
    runtime_health: dict[str, str] = Field(default_factory=dict)
    capabilities: RuntimeCapabilityCounts = Field(default_factory=RuntimeCapabilityCounts)
    tools: list[RuntimeToolDescriptorModel] = Field(default_factory=list)
    resources: list[RuntimeResourceDescriptorModel] = Field(default_factory=list)
    prompts: list[RuntimePromptDescriptorModel] = Field(default_factory=list)
    fl_capabilities: dict[str, object] = Field(default_factory=dict)
    provider_matrix: dict[str, dict[str, object]] = Field(default_factory=dict)
    provider_count: int = 0
    providers: list[dict[str, object]] = Field(default_factory=list)


class ManageProvidersResponse(BaseModel):
    status: Literal["ok", "partial", "error"]
    tool: Literal["manage_providers"] = "manage_providers"
    action: str
    provider_count: int = 0
    providers: list[dict[str, object]] = Field(default_factory=list)
    loaded: list[dict[str, object]] = Field(default_factory=list)
    errors: list[dict[str, object]] = Field(default_factory=list)
    loaded_count: int = 0
    error_count: int = 0
    started: int | None = None
    stopped: int | None = None
    error: str | None = None


class ProjectClipModel(BaseModel):
    clip_id: str
    name: str | None = None
    pattern_index: int | None = None
    start_beats: float = 0
    length_beats: float = 0
    track_index: int = 0
    muted: bool = False
    color: int | None = None


class ProjectMarkerModel(BaseModel):
    marker_id: str
    name: str
    position_beats: float = 0
    kind: str = "marker"


class ProjectArrangementTrackModel(BaseModel):
    track_index: int
    name: str
    clips: list[ProjectClipModel] = Field(default_factory=list)


class ProjectArrangementModel(BaseModel):
    selected_arrangement: str = "default"
    tracks: list[ProjectArrangementTrackModel] = Field(default_factory=list)
    markers: list[ProjectMarkerModel] = Field(default_factory=list)


class ProjectSnapshotResource(BaseModel):
    resource: Literal["project://snapshot"] = "project://snapshot"
    data: ProjectGraph = Field(default_factory=ProjectGraph)


class ProjectArrangementResource(BaseModel):
    resource: Literal["project://arrangement"] = "project://arrangement"
    data: ProjectArrangementModel = Field(default_factory=ProjectArrangementModel)


class ProviderTaskRecord(BaseModel):
    id: str
    kind: str
    provider: str
    state: TaskState
    message: str | None = None
    created_from_tool: str | None = None
    created_from_operation: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)


class RenderJobResource(BaseModel):
    resource: str
    data: ProviderTaskRecord


class AudioAnalysisResource(BaseModel):
    resource: str
    data: ProviderTaskRecord
