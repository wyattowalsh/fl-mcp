"""Plugin-profile registry, matching, calibration, and value mapping."""

from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fl_mcp.plugin_profiles.inventory import (
    clear_inventory_caches,
    normalize_plugin_id,
    plugin_profile_overlay_dir,
    scan_plugin_inventory,
    scan_preset_assets,
)
from fl_mcp.plugin_profiles.seeds import seed_profiles
from fl_mcp.schemas.plugin_profiles import (
    PluginCalibration,
    PluginControl,
    PluginInventoryItem,
    PluginPresetAsset,
    PluginProfile,
)

_REGISTRY_LOCK = threading.RLock()
_GLOBAL_REGISTRY: PluginProfileRegistry | None = None


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _all_profile_text(profile: PluginProfile) -> str:
    controls = " ".join(
        f"{control.control_id} {control.label}" for control in profile.semantic_controls
    )
    return " ".join(
        [
            profile.profile_id,
            profile.display_name,
            profile.family,
            profile.vendor or "",
            " ".join(profile.aliases),
            controls,
        ]
    )


def _score_text(query: str, text: str) -> int:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 1
    haystack_tokens = _tokens(text)
    score = 0
    for token in query_tokens:
        if token in haystack_tokens:
            score += 4
            continue
        if any(token in candidate or candidate in token for candidate in haystack_tokens):
            score += 1
            continue
        return 0
    if query.casefold() in text.casefold():
        score += 8
    return score


def _read_json_files(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists() or not directory.is_dir():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _status_rank(item: PluginInventoryItem | None) -> int:
    if item is None:
        return 0
    return {
        "not_installed": 0,
        "unknown": 1,
        "preset_only": 2,
        "filesystem_only": 3,
        "fl_database_only": 4,
        "installed": 5,
    }.get(item.status, 0)


class PluginProfileRegistry:
    """In-process registry for plugin profiles and local calibration overlays."""

    def __init__(
        self,
        *,
        profiles: list[PluginProfile] | None = None,
        calibrations: list[PluginCalibration] | None = None,
    ) -> None:
        seeded = profiles if profiles is not None else list(seed_profiles())
        self._profiles = {profile.profile_id: profile for profile in seeded}
        self._calibrations = {
            self._calibration_key(calibration): calibration
            for calibration in (
                calibrations if calibrations is not None else self._load_calibrations()
            )
        }

    @staticmethod
    def _calibration_key(calibration: PluginCalibration) -> tuple[str, str, str | None]:
        return (calibration.profile_id, calibration.format, calibration.fingerprint)

    @staticmethod
    def _load_calibrations() -> list[PluginCalibration]:
        calibrations: list[PluginCalibration] = []
        for payload in _read_json_files(plugin_profile_overlay_dir() / "calibrations"):
            try:
                calibrations.append(PluginCalibration.model_validate(payload))
            except ValidationError:
                continue
        return calibrations

    def clear_caches(self) -> None:
        """Clear filesystem inventory caches."""

        clear_inventory_caches()

    def profiles(self) -> tuple[PluginProfile, ...]:
        """Return profiles in deterministic id order."""

        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def profile(self, profile_id: str) -> PluginProfile | None:
        """Look up a profile by id, alias, or normalized plugin id."""

        normalized = normalize_plugin_id(profile_id)
        if profile_id in self._profiles:
            return self._profiles[profile_id]
        if normalized in self._profiles:
            return self._profiles[normalized]
        for profile in self.profiles():
            names = [profile.display_name, profile.family, *profile.aliases]
            if normalized in {normalize_plugin_id(name) for name in names}:
                return profile
        return None

    def inventory(self) -> tuple[PluginInventoryItem, ...]:
        """Return the merged local inventory, adding desired profiles absent from scans."""

        items = {item.plugin_id: item for item in scan_plugin_inventory()}
        for profile in self.profiles():
            if profile.profile_id in items:
                continue
            alias_ids = [normalize_plugin_id(alias) for alias in profile.aliases]
            existing = next((items[item] for item in alias_ids if item in items), None)
            if existing is not None:
                items[profile.profile_id] = existing.model_copy(
                    update={"plugin_id": profile.profile_id}
                )
                continue
            items[profile.profile_id] = PluginInventoryItem(
                plugin_id=profile.profile_id,
                display_name=profile.display_name,
                vendor=profile.vendor,
                kind=profile.kind,
                formats=list(profile.supported_formats),
                detected_by=["profile_seed"],
                status="not_installed" if profile.status == "desired" else "unknown",
            )
        return tuple(items[key] for key in sorted(items))

    def inventory_item(self, profile_or_plugin_id: str) -> PluginInventoryItem | None:
        """Return the best matching local inventory item for a profile or plugin id."""

        profile = self.profile(profile_or_plugin_id)
        candidates = [profile_or_plugin_id]
        if profile is not None:
            candidates.extend(
                [profile.profile_id, profile.display_name, profile.family, *profile.aliases]
            )
        normalized_candidates = {normalize_plugin_id(candidate) for candidate in candidates}
        best: PluginInventoryItem | None = None
        for item in self.inventory():
            item_names = {item.plugin_id, item.display_name}
            item_names.update(item.plugin_id.split("."))
            normalized_items = {normalize_plugin_id(name) for name in item_names}
            if normalized_candidates.isdisjoint(normalized_items):
                continue
            if best is None or _status_rank(item) > _status_rank(best):
                best = item
        return best

    def search(self, query: str | None, *, limit: int = 25) -> list[dict[str, object]]:
        """Search profiles and inventory together for browser/capability workflows."""

        query_text = (query or "").strip()
        results: list[tuple[int, int, dict[str, object]]] = []
        for index, profile in enumerate(self.profiles()):
            score = _score_text(query_text, _all_profile_text(profile))
            if query_text and score <= 0:
                continue
            inventory = self.inventory_item(profile.profile_id)
            results.append(
                (
                    score,
                    index,
                    {
                        "type": "profile",
                        "profile": profile.model_dump(mode="json"),
                        "inventory": inventory.model_dump(mode="json") if inventory else None,
                    },
                )
            )
        offset = len(results)
        for index, item in enumerate(self.inventory()):
            score = _score_text(
                query_text,
                " ".join(
                    [
                        item.plugin_id,
                        item.display_name,
                        item.vendor or "",
                        " ".join(item.detected_by),
                    ]
                ),
            )
            if query_text and score <= 0:
                continue
            results.append(
                (
                    score,
                    offset + index,
                    {"type": "inventory", "inventory": item.model_dump(mode="json")},
                )
            )
        ordered = [item[2] for item in sorted(results, key=lambda row: (-row[0], row[1]))]
        return ordered[: max(1, min(limit, 100))]

    def presets(self, query: str | None = None, *, limit: int = 100) -> list[PluginPresetAsset]:
        """Return local preset assets filtered by query."""

        query_text = (query or "").strip()
        results: list[tuple[int, int, PluginPresetAsset]] = []
        for index, asset in enumerate(scan_preset_assets()):
            text = " ".join(
                [
                    asset.path,
                    asset.inferred_plugin or "",
                    " ".join(asset.tags),
                    asset.source_pack or "",
                ]
            )
            score = _score_text(query_text, text)
            if query_text and score <= 0:
                continue
            results.append((score, index, asset))
        return [
            item[2]
            for item in sorted(results, key=lambda row: (-row[0], row[1]))[
                : max(1, min(limit, 500))
            ]
        ]

    def calibration_for(
        self,
        profile_id: str,
        *,
        plugin_format: str | None = None,
        fingerprint: str | None = None,
    ) -> PluginCalibration | None:
        """Return the best matching calibration for a profile."""

        profile = self.profile(profile_id)
        if profile is None:
            return None
        preferred_format = plugin_format or "unknown"
        keys = [
            (profile.profile_id, preferred_format, fingerprint),
            (profile.profile_id, preferred_format, None),
            (profile.profile_id, "unknown", fingerprint),
            (profile.profile_id, "unknown", None),
        ]
        for key in keys:
            calibration = self._calibrations.get(key)
            if calibration is not None:
                return calibration
        return None

    def upsert_calibration(self, calibration: PluginCalibration) -> None:
        """Add or replace one local calibration in the active registry."""

        self._calibrations[self._calibration_key(calibration)] = calibration

    def resolve_control(
        self,
        profile_id: str,
        control_id: str,
        *,
        plugin_format: str | None = None,
        fingerprint: str | None = None,
    ) -> tuple[PluginProfile | None, PluginControl | None, int | None, PluginCalibration | None]:
        """Resolve a semantic control to a calibrated parameter index if available."""

        profile = self.profile(profile_id)
        if profile is None:
            return None, None, None, None
        control = next(
            (item for item in profile.semantic_controls if item.control_id == control_id),
            None,
        )
        if control is None:
            return profile, None, None, None
        calibration = self.calibration_for(
            profile.profile_id,
            plugin_format=plugin_format,
            fingerprint=fingerprint,
        )
        parameter_index = None
        if calibration is not None:
            parameter_index = calibration.mapped_controls.get(control.control_id)
        if parameter_index is None:
            parameter_index = control.parameter_index
        return profile, control, parameter_index, calibration


def normalize_control_value(control: PluginControl, value: float | int | str) -> float:
    """Convert a plain semantic value to FL's 0..1 normalized parameter range."""

    value_map = control.value_map
    if isinstance(value, str):
        if value_map.kind == "enum":
            try:
                index = value_map.enum_values.index(value)
            except ValueError as exc:
                msg = f"unknown enum value for {control.control_id}: {value}"
                raise ValueError(msg) from exc
            if len(value_map.enum_values) <= 1:
                return 0.0
            return index / float(len(value_map.enum_values) - 1)
        try:
            numeric = float(value)
        except ValueError as exc:
            msg = f"control {control.control_id} requires a numeric value"
            raise ValueError(msg) from exc
    else:
        numeric = float(value)

    if value_map.kind == "normalized":
        normalized = numeric
    elif value_map.kind == "percent":
        normalized = numeric / 100.0 if numeric > 1 else numeric
    elif value_map.kind == "bipolar":
        if not -1 <= numeric <= 1:
            msg = f"bipolar control {control.control_id} requires -1..1"
            raise ValueError(msg)
        normalized = (numeric + 1.0) / 2.0
    elif value_map.kind in {"linear", "db", "milliseconds", "note_pitch"}:
        if value_map.min_value is None or value_map.max_value is None:
            normalized = numeric
        else:
            span = value_map.max_value - value_map.min_value
            if span <= 0:
                msg = f"invalid value-map span for {control.control_id}"
                raise ValueError(msg)
            normalized = (numeric - value_map.min_value) / span
    elif value_map.kind == "log_frequency":
        if value_map.min_value is None or value_map.max_value is None:
            msg = f"log-frequency control {control.control_id} requires min/max"
            raise ValueError(msg)
        if numeric <= 0:
            msg = f"log-frequency control {control.control_id} requires value > 0"
            raise ValueError(msg)
        min_log = math.log(value_map.min_value)
        max_log = math.log(value_map.max_value)
        normalized = (math.log(numeric) - min_log) / (max_log - min_log)
    else:
        normalized = numeric

    if not 0 <= normalized <= 1:
        msg = f"normalized value for {control.control_id} out of range: {normalized}"
        raise ValueError(msg)
    return float(normalized)


def get_plugin_profile_registry() -> PluginProfileRegistry:
    """Return the singleton plugin-profile registry."""

    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        if _GLOBAL_REGISTRY is None:
            _GLOBAL_REGISTRY = PluginProfileRegistry()
        return _GLOBAL_REGISTRY


def reset_plugin_profile_registry() -> None:
    """Reset plugin-profile registry and filesystem scan caches."""

    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        _GLOBAL_REGISTRY = None
        clear_inventory_caches()
