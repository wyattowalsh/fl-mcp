"""In-process provider runtime core."""

from __future__ import annotations

import importlib
import logging
import threading
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, cast

from fl_mcp.exceptions import ProviderError
from fl_mcp.providers.adapters import LegacyProviderAdapter, ProviderAdapter
from fl_mcp.providers.builtin import builtin_providers
from fl_mcp.schemas import ProviderManifest
from fl_mcp.schemas.provider import (
    ProviderAdapterTaskRecord,
    ProviderHealthReport,
    ProviderOperationResult,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProviderStatus:
    """Provider status entry exposed via management tools."""

    manifest: ProviderManifest
    state: str = "registered"
    source: str = "direct"
    health: ProviderHealthReport = field(default_factory=ProviderHealthReport)

    def model_dump(self) -> dict[str, object]:
        """Serialize the status entry to a plain dictionary."""
        return {
            "manifest": self.manifest.model_dump(),
            "state": self.state,
            "source": self.source,
            "health": self.health.model_dump(),
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
        """Serialize the discovery error to a plain dictionary."""
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


_REGISTRY_LOCK = threading.RLock()


class ProviderRegistry:
    """Provider registry and lifecycle manager."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}
        self._status: dict[str, ProviderStatus] = {}
        self._aliases: dict[str, str] = {}
        self._entry_points_loaded: bool = False
        self._entry_point_errors: list[ProviderDiscoveryError] = []

    def register(self, provider: Any, *, source: str = "direct") -> ProviderManifest:
        """Register a provider and return its validated manifest.

        Args:
            provider: A provider object or adapter conforming to the
                ``ProviderAdapter`` protocol.
            source: Label indicating how the provider was discovered
                (e.g. ``"builtin"``, ``"entry-point:name"``).
        """
        adapter = _ensure_adapter(provider)
        manifest = ProviderManifest.model_validate(adapter.manifest)
        with _REGISTRY_LOCK:
            self._providers[manifest.name] = adapter
            self._status[manifest.name] = ProviderStatus(
                manifest=manifest,
                source=source,
                health=adapter.health(),
            )
            self._aliases[manifest.name] = manifest.name
            for alias in manifest.aliases:
                self._aliases[alias] = manifest.name
        logger.info("Registering provider %s from %s", manifest.name, source)
        return manifest

    def manifests(self) -> list[ProviderManifest]:
        """Return the list of manifests for all registered providers."""
        return [status.manifest for status in self._status.values()]

    def statuses(self) -> list[dict[str, object]]:
        """Return serialized status entries for all providers, refreshing health first."""
        with _REGISTRY_LOCK:
            for name, provider in self._providers.items():
                self._status[name].health = provider.health()
            return [self._status[name].model_dump() for name in sorted(self._status.keys())]

    def resolve_name(self, provider_name: str) -> str:
        """Resolve a provider name or alias to its canonical name."""
        return self._aliases.get(provider_name, provider_name)

    def get(self, provider_name: str) -> ProviderAdapter:
        """Look up a provider adapter by name or alias.

        Raises:
            KeyError: If no provider matches the given name.
        """
        canonical_name = self.resolve_name(provider_name)
        try:
            return self._providers[canonical_name]
        except KeyError as exc:
            msg = f"Unknown provider '{provider_name}'."
            raise ProviderError(msg) from exc

    def supports(self, provider_name: str, capability: str) -> bool:
        """Check whether a named provider supports a given capability."""
        return self.get(provider_name).supports(capability)

    def execute(
        self,
        provider_name: str,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderOperationResult:
        """Dispatch a domain operation to the named provider."""
        return self.get(provider_name).execute(
            domain=domain,
            operation=operation,
            payload=payload,
        )

    def read_resource(self, provider_name: str, uri: str) -> dict[str, object] | None:
        """Read a provider-scoped resource by URI."""
        return self.get(provider_name).read_resource(uri)

    def start_task(
        self,
        provider_name: str,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderAdapterTaskRecord:
        """Start an asynchronous task on the named provider."""
        return self.get(provider_name).start_task(
            domain=domain,
            operation=operation,
            payload=payload,
        )

    def poll_task(self, provider_name: str, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Poll a task's current state on the named provider."""
        return self.get(provider_name).poll_task(task_id)

    def cancel_task(self, provider_name: str, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Cancel a running task on the named provider."""
        return self.get(provider_name).cancel_task(task_id)

    def health(self, provider_name: str) -> ProviderHealthReport:
        """Return the health report for the named provider."""
        return self.get(provider_name).health()

    def startup_all(self) -> int:
        """Start all registered providers and return the count of started providers."""
        manifests = self.manifests()
        logger.info("Starting %d providers", len(manifests))
        with _REGISTRY_LOCK:
            started = 0
            failures: list[tuple[str, Exception]] = []
            for name, provider in self._providers.items():
                try:
                    provider.startup()
                except Exception as exc:
                    logger.warning(
                        "Provider %s failed during startup: %s",
                        name,
                        exc,
                        exc_info=True,
                    )
                    self._status[name].state = "failed"
                    failures.append((name, exc))
                    continue
                self._status[name].state = "running"
                self._status[name].health = provider.health()
                started += 1
            if started == 0 and failures:
                summary = "; ".join(f"{n}: {e}" for n, e in failures)
                raise ProviderError(f"All providers failed during startup: {summary}")
            return started

    def shutdown_all(self) -> int:
        """Shut down all registered providers and return the count of stopped providers."""
        manifests = self.manifests()
        logger.info("Shutting down %d providers", len(manifests))
        with _REGISTRY_LOCK:
            stopped = 0
            for name, provider in self._providers.items():
                provider.shutdown()
                self._status[name].state = "stopped"
                self._status[name].health = provider.health()
                stopped += 1
            return stopped

    def load_from_module(self, module_path: str) -> ProviderManifest:
        """Import a module by dotted path and register its provider.

        The module must export either a ``provider`` attribute or a
        ``create_provider()`` callable.

        Raises:
            ValueError: If the module does not export a valid provider.
        """
        module = importlib.import_module(module_path)
        candidate = getattr(module, "provider", None)
        if candidate is None:
            factory = getattr(module, "create_provider", None)
            if callable(factory):
                candidate = factory()
        if candidate is None:
            msg = f"Provider module '{module_path}' must export 'provider' or 'create_provider'."
            raise ProviderError(msg)
        # register() already acquires _REGISTRY_LOCK internally
        return self.register(candidate, source=f"module:{module_path}")

    def load_from_entry_points(
        self,
        group: str = "fl_mcp.providers",
    ) -> ProviderDiscoveryResult:
        """Discover and register providers from setuptools entry points.

        Args:
            group: Entry-point group name to scan.

        Returns:
            A discovery result containing loaded manifests and any errors.
        """
        with _REGISTRY_LOCK:
            if self._entry_points_loaded:
                return ProviderDiscoveryResult(
                    loaded=self.manifests(),
                    errors=list(self._entry_point_errors),
                )
            loaded: list[ProviderManifest] = []
            errors: list[ProviderDiscoveryError] = []
            for entry_point in _entry_points_for_group(group):
                try:
                    provider = entry_point.load()
                    # register() also acquires _REGISTRY_LOCK but it is an RLock
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


def _ensure_adapter(provider: Any) -> ProviderAdapter:
    manifest = ProviderManifest.model_validate(provider.manifest)
    required = (
        "supports",
        "execute",
        "read_resource",
        "start_task",
        "poll_task",
        "cancel_task",
        "startup",
        "shutdown",
        "health",
    )
    if all(hasattr(provider, attr) for attr in required):
        provider.manifest = manifest
        return cast(ProviderAdapter, provider)
    return cast(
        ProviderAdapter,
        LegacyProviderAdapter(provider=provider, manifest=manifest),
    )


_GLOBAL_REGISTRY: ProviderRegistry | None = None


def get_provider_registry(*, load_entry_points: bool = True) -> ProviderRegistry:
    """Return singleton provider registry used by runtime tool handlers."""
    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        if _GLOBAL_REGISTRY is None:
            _GLOBAL_REGISTRY = ProviderRegistry()
            for provider in builtin_providers():
                _GLOBAL_REGISTRY.register(provider, source="builtin")
    if load_entry_points:
        _GLOBAL_REGISTRY.load_from_entry_points()
    return _GLOBAL_REGISTRY


def reset_provider_registry() -> None:
    """Reset global provider registry for deterministic tests."""
    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        _GLOBAL_REGISTRY = None
