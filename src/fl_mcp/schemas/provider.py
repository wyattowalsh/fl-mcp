"""Provider manifest and adapter schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from fl_mcp.schemas._types import TaskState

ProviderMaturity = Literal["experimental", "beta", "stable"]
ProviderHealthStatus = Literal["ok", "warning", "error", "disabled"]

# Backward-compatible alias kept for downstream consumers.
ProviderTaskState = TaskState


class ProviderManifest(BaseModel):
    """Provider registration model."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    maturity: ProviderMaturity = "experimental"
    entrypoint: str | None = None
    description: str | None = None
    enabled: bool = True
    supported_domains: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    task_kinds: list[str] = Field(default_factory=list)

    def __getitem__(self, key: str) -> object:
        try:
            return getattr(self, key)
        except AttributeError as exc:  # pragma: no cover - defensive compatibility path
            raise KeyError(key) from exc

    @field_validator("capabilities", "supported_domains", "aliases", "resources", "task_kinds")
    @classmethod
    def _normalize_unique_sorted(cls, values: list[str]) -> list[str]:
        return sorted({value.strip() for value in values if value.strip()})


class ProviderHealthReport(BaseModel):
    """Health details for one provider adapter."""

    status: ProviderHealthStatus = "ok"
    details: dict[str, object] = Field(default_factory=dict)


class ProviderOperationResult(BaseModel):
    """Normalized provider execution result."""

    success: bool
    provider: str
    message: str
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None
    execution_id: str | None = None
    bridge_mode: str | None = None


class ProviderAdapterTaskRecord(BaseModel):
    """Stored task state for provider-backed long-running operations.

    Named ``ProviderAdapterTaskRecord`` to avoid collision with the
    runtime-surface ``ProviderTaskRecord`` in ``schemas.runtime_surface``.
    """

    task_id: str
    provider: str
    operation: str
    state: TaskState = "queued"
    message: str | None = None
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None


class ProviderRuntimeStatus(BaseModel):
    """Runtime health/status for a registered provider."""

    name: str
    version: str
    maturity: ProviderMaturity = "experimental"
    started: bool = False
    capabilities: list[str] = Field(default_factory=list)
    supported_domains: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    health: ProviderHealthReport = Field(default_factory=ProviderHealthReport)
