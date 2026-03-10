"""In-process provider runtime core."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Protocol, cast

from fl_mcp.schemas import ProviderManifest


class Provider(Protocol):
    manifest: ProviderManifest | dict[str, Any]

    def startup(self) -> None: ...

    def shutdown(self) -> None: ...


@dataclass(slots=True)
class ProviderStatus:
    """Provider status entry exposed via management tools."""

    manifest: ProviderManifest
    state: str = "registered"
    source: str = "direct"

    def model_dump(self) -> dict[str, object]:
        return {
            "manifest": self.manifest.model_dump(),
            "state": self.state,
            "source": self.source,
        }


@dataclass(slots=True)
class ProviderDiscoveryError:
    """Structured discovery error for provider entry-point loading."""

    group: str
    entry_point: str
    value: str
    error_type: str
    message: str

    def model_dump(self) -> dict[str, str]:
        return {
            "group": self.group,
            "entry_point": self.entry_point,
            "value": self.value,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass(slots=True)
class ProviderDiscoveryResult:
    """Aggregated provider discovery outcome."""

    loaded: list[ProviderManifest]
    errors: list[ProviderDiscoveryError]


def _entry_points_for_group(group: str) -> list[metadata.EntryPoint]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = list(entry_points.select(group=group))
    else:
        grouped = cast(dict[str, list[metadata.EntryPoint]], entry_points)
        selected = grouped.get(group, [])
    return selected


class ProviderRegistry:
    """Provider registry and lifecycle manager."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._status: dict[str, ProviderStatus] = {}
        self._entry_points_loaded: bool = False
        self._entry_point_errors: list[ProviderDiscoveryError] = []

    def register(self, provider: Provider, *, source: str = "direct") -> ProviderManifest:
        manifest = ProviderManifest.model_validate(provider.manifest)
        self._providers[manifest.name] = provider
        self._status[manifest.name] = ProviderStatus(manifest=manifest, source=source)
        return manifest

    def manifests(self) -> list[ProviderManifest]:
        return [status.manifest for status in self._status.values()]

    def statuses(self) -> list[dict[str, object]]:
        return [self._status[name].model_dump() for name in sorted(self._status.keys())]

    def startup_all(self) -> int:
        started = 0
        for name, provider in self._providers.items():
            provider.startup()
            self._status[name].state = "running"
            started += 1
        return started

    def shutdown_all(self) -> int:
        stopped = 0
        for name, provider in self._providers.items():
            provider.shutdown()
            self._status[name].state = "stopped"
            stopped += 1
        return stopped

    def load_from_module(self, module_path: str) -> ProviderManifest:
        module = importlib.import_module(module_path)
        candidate = getattr(module, "provider", None)
        if candidate is None:
            factory = getattr(module, "create_provider", None)
            if callable(factory):
                candidate = factory()
        if candidate is None:
            msg = f"Provider module '{module_path}' must export 'provider' or 'create_provider'."
            raise ValueError(msg)
        provider = cast(Provider, candidate)
        return self.register(provider, source=f"module:{module_path}")

    def load_from_entry_points(
        self,
        group: str = "fl_mcp.providers",
    ) -> ProviderDiscoveryResult:
        if self._entry_points_loaded:
            return ProviderDiscoveryResult(
                loaded=self.manifests(),
                errors=list(self._entry_point_errors),
            )
        loaded: list[ProviderManifest] = []
        errors: list[ProviderDiscoveryError] = []
        for entry_point in _entry_points_for_group(group):
            try:
                provider = cast(Provider, entry_point.load())
                loaded.append(self.register(provider, source=f"entry-point:{entry_point.name}"))
            except Exception as exc:  # pragma: no cover - covered through behavior contract
                errors.append(
                    ProviderDiscoveryError(
                        group=group,
                        entry_point=entry_point.name,
                        value=entry_point.value,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
        self._entry_point_errors = errors
        self._entry_points_loaded = True
        return ProviderDiscoveryResult(loaded=loaded, errors=errors)


_GLOBAL_REGISTRY: ProviderRegistry | None = None


def get_provider_registry(*, load_entry_points: bool = True) -> ProviderRegistry:
    """Return singleton provider registry used by runtime tool handlers."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ProviderRegistry()
    if load_entry_points:
        _GLOBAL_REGISTRY.load_from_entry_points()
    return _GLOBAL_REGISTRY


def reset_provider_registry() -> None:
    """Reset global provider registry for deterministic tests."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = None
