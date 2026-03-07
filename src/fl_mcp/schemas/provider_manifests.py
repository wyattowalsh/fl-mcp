"""Provider manifest schemas for planner/apply capability discovery."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .transactions import RollbackClassification


class ProviderCapability(BaseModel):
    """Capability a provider exposes to planning/apply orchestration."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Capability name.")
    description: str = Field(..., description="Human-readable capability summary.")


class ProviderOperation(BaseModel):
    """Single provider operation definition."""

    model_config = ConfigDict(extra="forbid")

    operation: str = Field(..., description="Canonical operation key.")
    rollback_classification: RollbackClassification = Field(
        ..., description="Rollback/checkpoint classification for this operation."
    )
    idempotent: bool = Field(..., description="Whether operation can be safely retried.")


class ProviderManifest(BaseModel):
    """Provider descriptor consumed by planning and apply pipelines."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(..., description="Provider identifier.")
    version: str = Field(..., description="Provider semantic version.")
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    operations: list[ProviderOperation] = Field(default_factory=list)
