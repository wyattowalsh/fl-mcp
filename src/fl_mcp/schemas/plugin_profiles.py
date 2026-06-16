"""Typed schemas for plugin-profile inventory, calibration, and controls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

PluginKind = Literal["instrument", "effect", "instrument_or_effect", "unknown"]
PluginFormat = Literal["au", "vst", "vst3", "clap", "fst", "fxp", "fxb", "unknown"]
PluginInventoryStatus = Literal[
    "installed",
    "filesystem_only",
    "fl_database_only",
    "preset_only",
    "not_installed",
    "unknown",
]
PluginSupportPriority = Literal[
    "P0_paid_installed",
    "P1_paid_detected_or_suite",
    "P2_popular_useful_stock_or_free",
    "P3_inventory_only_on_demand",
    "desired_not_installed",
]
PluginSupportState = Literal[
    "inventory_stub",
    "loadable",
    "raw_enumerated",
    "semantic_seed",
    "calibrated",
    "verified",
    "desired",
    "not_installed",
    "unloadable",
    "unprobeable",
    "unsupported_host_behavior",
]
PluginProfileStatus = Literal["verified", "partial", "seed", "stub", "desired", "unsupported"]
PluginControlRisk = Literal["read", "safe", "creative", "destructive", "volatile"]
PluginControlOrigin = Literal[
    "live_raw",
    "curated_semantic",
    "vendor_seed",
    "generated_stub",
    "preset_asset",
]
PluginWriteProbeStatus = Literal[
    "not_run",
    "skipped",
    "read_only",
    "writable",
    "failed",
    "restored",
]
PluginValueMapKind = Literal[
    "normalized",
    "linear",
    "log_frequency",
    "db",
    "enum",
    "percent",
    "bipolar",
    "milliseconds",
    "tempo_synced",
    "note_pitch",
    "custom",
]
PluginPresetKind = Literal["preset", "bank", "wrapper_state", "unknown"]
PluginPresetSafety = Literal["available", "path_unavailable", "plugin_mismatch", "unsupported"]
PluginProfileFailureCode = Literal[
    "plugin_not_installed",
    "plugin_not_in_fl_database",
    "format_ambiguous",
    "profile_missing",
    "profile_unverified",
    "calibration_required",
    "parameter_unmapped",
    "parameter_count_mismatch",
    "preset_unavailable",
    "midi_routing_required",
    "live_probe_failed",
    "readback_mismatch",
]


def _normalize_unique(values: list[str]) -> list[str]:
    return sorted({value.strip() for value in values if value.strip()})


class PluginInventoryItem(BaseModel):
    """One locally discovered plugin or preset-backed plugin candidate."""

    plugin_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    vendor: str | None = None
    kind: PluginKind = "unknown"
    formats: list[PluginFormat] = Field(default_factory=list)
    bundle_paths: list[str] = Field(default_factory=list)
    fl_database_entries: list[str] = Field(default_factory=list)
    favorite_entries: list[str] = Field(default_factory=list)
    preset_paths: list[str] = Field(default_factory=list)
    detected_by: list[str] = Field(default_factory=list)
    status: PluginInventoryStatus = "unknown"

    @field_validator(
        "formats",
        "bundle_paths",
        "fl_database_entries",
        "favorite_entries",
        "preset_paths",
        "detected_by",
    )
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)


class PluginValueMap(BaseModel):
    """Mapping from semantic plain values to FL's normalized plugin values."""

    kind: PluginValueMapKind = "normalized"
    min_value: float | None = None
    max_value: float | None = None
    default_value: float | str | None = None
    enum_values: list[str] = Field(default_factory=list)
    expression: str | None = None

    @field_validator("enum_values")
    @classmethod
    def _dedupe_enum_values(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)


class PluginRawParameter(BaseModel):
    """One FL-exposed automatable plugin parameter discovered through live probing."""

    parameter_index: int = Field(ge=0)
    parameter_name: str | None = None
    normalized_value: float | None = Field(default=None, ge=0, le=1)
    value_string: str | None = None
    readable: bool = True
    writable: bool | None = None
    write_probe_status: PluginWriteProbeStatus = "not_run"
    risk: PluginControlRisk = "safe"
    control_origin: PluginControlOrigin = "live_raw"


class PluginWrapperFingerprint(BaseModel):
    """Local wrapper identity used to detect stale parameter mappings."""

    plugin_name: str | None = None
    format: PluginFormat = "unknown"
    parameter_count: int | None = Field(default=None, ge=0)
    parameter_name_hash: str | None = None
    fl_version: str | None = None
    bridge_mode: str | None = None


class PluginControl(BaseModel):
    """A semantic plugin control that may resolve to a local FL parameter index."""

    control_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    group: str = "main"
    unit: str | None = None
    value_map: PluginValueMap = Field(default_factory=PluginValueMap)
    parameter_index: int | None = Field(default=None, ge=0)
    parameter_name_hint: str | None = None
    control_origin: PluginControlOrigin = "curated_semantic"
    readback: bool = True
    risk: PluginControlRisk = "safe"
    requires_window: bool = False
    requires_midi: bool = False
    midi_cc: int | None = Field(default=None, ge=0, le=127)


class PluginProfile(BaseModel):
    """Declarative plugin support profile."""

    profile_id: str = Field(min_length=1)
    vendor: str | None = None
    family: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    kind: PluginKind = "unknown"
    supported_formats: list[PluginFormat] = Field(default_factory=list)
    semantic_controls: list[PluginControl] = Field(default_factory=list)
    preset_loaders: list[PluginFormat] = Field(default_factory=list)
    routing_requirements: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    support_priority: PluginSupportPriority = "P3_inventory_only_on_demand"
    support_state: PluginSupportState | None = None
    raw_parameters: list[PluginRawParameter] = Field(default_factory=list)
    wrapper_fingerprint: PluginWrapperFingerprint | None = None
    coverage_evidence: dict[str, object] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)
    status: PluginProfileStatus = "stub"

    @field_validator("aliases", "routing_requirements", "provenance")
    @classmethod
    def _dedupe_strings(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)

    @field_validator("supported_formats", "preset_loaders")
    @classmethod
    def _dedupe_formats(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)


class PluginCalibration(BaseModel):
    """Machine-local learned mapping from semantic controls to FL parameter indices."""

    profile_id: str = Field(min_length=1)
    format: PluginFormat = "unknown"
    fl_reported_name: str | None = None
    parameter_count: int | None = Field(default=None, ge=0)
    mapped_controls: dict[str, int] = Field(default_factory=dict)
    verified_at: str | None = None
    bridge_mode: str | None = None
    source: str = "local"
    fingerprint: str | None = None

    @field_validator("mapped_controls")
    @classmethod
    def _validate_parameter_indices(cls, values: dict[str, int]) -> dict[str, int]:
        for key, value in values.items():
            if not key.strip():
                msg = "mapped control ids must be non-empty"
                raise ValueError(msg)
            if value < 0:
                msg = "mapped parameter indices must be non-negative"
                raise ValueError(msg)
        return dict(sorted(values.items()))


class PluginPresetAsset(BaseModel):
    """Preset, bank, or wrapper-state asset discovered on disk."""

    path: str = Field(min_length=1)
    extension: PluginFormat = "unknown"
    inferred_plugin: str | None = None
    kind: PluginPresetKind = "unknown"
    bank_or_single: Literal["bank", "single", "unknown"] = "unknown"
    tags: list[str] = Field(default_factory=list)
    source_pack: str | None = None
    safety: PluginPresetSafety = "available"

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)


class PluginSupportMatrixRow(BaseModel):
    """Priority support row used by plugin coverage audits and exported matrices."""

    plugin_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    priority: PluginSupportPriority
    support_state: PluginSupportState
    inventory_status: PluginInventoryStatus
    profile_id: str | None = None
    profile_status: PluginProfileStatus | None = None
    semantic_control_count: int = Field(default=0, ge=0)
    raw_parameter_count: int = Field(default=0, ge=0)
    formats: list[PluginFormat] = Field(default_factory=list)
    detected_by: list[str] = Field(default_factory=list)
    failure_code: PluginProfileFailureCode | None = None
    remediation: str | None = None

    @field_validator("formats", "detected_by")
    @classmethod
    def _dedupe_matrix_lists(cls, values: list[str]) -> list[str]:
        return _normalize_unique(values)
