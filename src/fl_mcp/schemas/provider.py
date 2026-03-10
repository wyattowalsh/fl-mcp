"""Provider manifest schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderMaturity = Literal["experimental", "beta", "stable"]


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

    @field_validator("capabilities", "supported_domains")
    @classmethod
    def _normalize_unique_sorted(cls, values: list[str]) -> list[str]:
        return sorted({value.strip() for value in values if value.strip()})


class ProviderRuntimeStatus(BaseModel):
    """Runtime health/status for a registered provider."""

    name: str
    version: str
    maturity: ProviderMaturity = "experimental"
    started: bool = False
    capabilities: list[str] = Field(default_factory=list)
