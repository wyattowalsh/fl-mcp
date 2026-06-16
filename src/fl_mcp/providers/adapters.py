"""Provider adapter implementations for bridge-backed runtime execution."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from uuid import uuid4

from fl_mcp.bridge.fl_studio import FLStudioBridge
from fl_mcp.schemas.provider import (
    ProviderAdapterTaskRecord,
    ProviderHealthReport,
    ProviderManifest,
    ProviderMaturity,
    ProviderOperationResult,
    ProviderTaskState,
)
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS


class ProviderAdapter(Protocol):
    """Execution contract for runtime providers."""

    manifest: ProviderManifest | dict[str, object]

    def supports(self, capability: str, /) -> bool:
        """Return whether the provider supports the given capability or domain."""
        ...

    def execute(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderOperationResult:
        """Execute a domain operation and return a structured result."""
        ...

    def read_resource(self, uri: str) -> dict[str, object] | None:
        """Read a provider-scoped resource by URI, or ``None`` if not found."""
        ...

    def start_task(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderAdapterTaskRecord:
        """Start an asynchronous task and return its initial record."""
        ...

    def poll_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Poll the current state of a previously started task."""
        ...

    def cancel_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Request cancellation of a running task."""
        ...

    def startup(self) -> None:
        """Perform provider startup and resource acquisition."""
        ...

    def shutdown(self) -> None:
        """Release provider resources and stop background work."""
        ...

    def health(self) -> ProviderHealthReport:
        """Return a structured health report for the provider."""
        ...


def _capabilities_for_domains(domains: list[str]) -> list[str]:
    supported_domains = set(domains)
    return sorted(spec.name for spec in FL_TOOL_SPECS if spec.domain in supported_domains)


def _operation_capability_name(domain: str, operation: str) -> str:
    return f"{domain}_{operation}".replace("-", "_")


def _task_state(value: object) -> ProviderTaskState:
    if value == "cancelled":
        return "canceled"
    if value in {"queued", "running", "completed", "failed", "canceled"}:
        return cast(ProviderTaskState, value)
    return "queued"


@dataclass(slots=True)
class BridgeBackedProvider:
    """Provider adapter delegating execution to the shared FL Studio bridge."""

    manifest: ProviderManifest
    bridge_provider: str
    _started: bool = False
    _bridge: FLStudioBridge | None = None
    _tasks: dict[str, ProviderAdapterTaskRecord] = field(default_factory=dict)
    _task_lock: threading.Lock = field(default_factory=threading.Lock)

    def supports(self, capability: str, /) -> bool:
        """Return whether this provider supports the given capability or domain."""
        if capability in self.manifest.capabilities:
            return True
        if capability == "all" and "all" in self.manifest.capabilities:
            return True
        return False

    def execute(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderOperationResult:
        """Execute a domain operation via the underlying FL Studio bridge."""
        capability = _operation_capability_name(domain, operation)
        if "all" not in self.manifest.capabilities and capability not in self.manifest.capabilities:
            return ProviderOperationResult(
                success=False,
                provider=self.manifest.name,
                message=(
                    f"Provider '{self.manifest.name}' does not support "
                    f"operation '{domain}.{operation}'."
                ),
                error_code="unsupported_capability",
                result={
                    "supported_domains": list(self.manifest.supported_domains),
                    "capabilities": list(self.manifest.capabilities),
                },
            )

        if self._bridge is None:
            self.startup()
        bridge = self._bridge
        if bridge is None:
            return ProviderOperationResult(
                success=False,
                provider=self.manifest.name,
                message=f"Provider '{self.manifest.name}' bridge startup did not initialize.",
                error_code="provider_startup_failed",
                result={},
            )
        bridge_result = bridge.execute_operation(
            domain=domain,
            operation=operation,
            payload=payload,
            provider=self.bridge_provider,
        )
        return ProviderOperationResult(
            success=bridge_result.success,
            provider=self.manifest.name,
            message=bridge_result.message,
            result=bridge_result.result,
            error_code=bridge_result.error_code,
            execution_id=bridge_result.execution_id,
            bridge_mode=bridge_result.bridge_mode,
        )

    def read_resource(self, uri: str) -> dict[str, object] | None:
        """Read a provider resource (catalog, health, or task) by URI."""
        if uri == f"providers://{self.manifest.name}/catalog":
            return self.manifest.model_dump()
        if uri == f"providers://{self.manifest.name}/health":
            return self.health().model_dump()
        if uri.startswith(f"providers://{self.manifest.name}/tasks/"):
            task_id = uri.rsplit("/", 1)[-1]
            task = self.poll_task(task_id)
            return task.model_dump() if task is not None else None
        return None

    def start_task(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderAdapterTaskRecord:
        """Start an asynchronous task by executing the operation immediately."""
        execution = self.execute(domain=domain, operation=operation, payload=payload)
        task_id = execution.execution_id or f"{self.manifest.name}-{uuid4().hex[:12]}"
        task = ProviderAdapterTaskRecord(
            task_id=task_id,
            provider=self.manifest.name,
            operation=f"{domain}.{operation}",
            state=(
                _task_state(execution.result.get("task_status", "queued"))
                if execution.success
                else "failed"
            ),
            message=execution.message,
            result=execution.result,
            error_code=execution.error_code,
        )
        with self._task_lock:
            self._tasks[task_id] = task
        return task

    def poll_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Return the current state of a task, or ``None`` if unknown."""
        with self._task_lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Cancel a running task if it has not already reached a terminal state."""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.state in {"completed", "failed", "canceled"}:
                return task
            task.state = "canceled"
            task.message = task.message or "Task canceled."
            return task

    def startup(self) -> None:
        """Initialize the underlying FL Studio bridge from the environment."""
        self._bridge = FLStudioBridge.from_environment()
        self._started = True

    def shutdown(self) -> None:
        """Release the bridge connection and reset internal state."""
        self._bridge = None
        self._started = False

    def health(self) -> ProviderHealthReport:
        """Return a health report including domain support and task counts."""
        return ProviderHealthReport(
            status="ok" if self.manifest.enabled else "disabled",
            details={
                "started": self._started,
                "supported_domains": list(self.manifest.supported_domains),
                "task_count": len(self._tasks),
                "resources": list(self.manifest.resources),
                "task_kinds": list(self.manifest.task_kinds),
            },
        )


@dataclass(slots=True)
class LegacyProviderAdapter:
    """Wrapper making manifest-only providers conform to the adapter contract."""

    provider: Any
    manifest: ProviderManifest
    _started: bool = False
    _task_lock: threading.Lock = field(default_factory=threading.Lock)

    def supports(self, capability: str, /) -> bool:
        """Return whether this legacy provider supports the given capability."""
        return (
            capability in self.manifest.capabilities
            or capability in self.manifest.supported_domains
        )

    def execute(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderOperationResult:
        """Always return a failure since legacy providers lack runtime execution."""
        return ProviderOperationResult(
            success=False,
            provider=self.manifest.name,
            message=(
                f"Provider '{self.manifest.name}' does not implement runtime execution "
                f"for '{domain}.{operation}'."
            ),
            error_code="unsupported_capability",
            result={},
        )

    def read_resource(self, uri: str) -> dict[str, object] | None:
        """Read the catalog or health resource for this provider."""
        if uri == f"providers://{self.manifest.name}/catalog":
            return self.manifest.model_dump()
        if uri == f"providers://{self.manifest.name}/health":
            return self.health().model_dump()
        return None

    def start_task(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
    ) -> ProviderAdapterTaskRecord:
        """Start a task; always fails for legacy providers."""
        with self._task_lock:
            result = self.execute(domain=domain, operation=operation, payload=payload)
            return ProviderAdapterTaskRecord(
                task_id=f"{self.manifest.name}-{uuid4().hex[:12]}",
                provider=self.manifest.name,
                operation=f"{domain}.{operation}",
                state="failed",
                message=result.message,
                result=result.result,
                error_code=result.error_code,
            )

    def poll_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Always returns ``None``; legacy providers do not track tasks."""
        with self._task_lock:
            return None

    def cancel_task(self, task_id: str) -> ProviderAdapterTaskRecord | None:
        """Always returns ``None``; legacy providers do not track tasks."""
        with self._task_lock:
            return None

    def startup(self) -> None:
        """Delegate startup to the wrapped provider if it exposes one."""
        if hasattr(self.provider, "startup"):
            self.provider.startup()
        self._started = True

    def shutdown(self) -> None:
        """Delegate shutdown to the wrapped provider if it exposes one."""
        if hasattr(self.provider, "shutdown"):
            self.provider.shutdown()
        self._started = False

    def health(self) -> ProviderHealthReport:
        """Return a health report flagged as legacy."""
        return ProviderHealthReport(
            status="ok" if self.manifest.enabled else "disabled",
            details={"started": self._started, "legacy": True},
        )


def build_manifest(
    *,
    name: str,
    description: str,
    supported_domains: list[str],
    maturity: ProviderMaturity,
    aliases: list[str] | None = None,
    resources: list[str] | None = None,
    task_kinds: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> ProviderManifest:
    """Construct a ``ProviderManifest`` with auto-derived capabilities.

    Capabilities are inferred from the FL tool spec surface that matches the
    given ``supported_domains`` unless an operation-specific list is supplied.

    Args:
        name: Unique provider identifier.
        description: Human-readable description of the provider.
        supported_domains: FL Studio domains this provider can serve.
        maturity: Maturity tier (``"stable"``, ``"beta"``, ``"experimental"``).
        aliases: Optional alternative names for provider resolution.
        resources: Optional explicit resource URIs; defaults are generated.
        task_kinds: Optional task kind identifiers the provider can handle.
        capabilities: Optional explicit capability/tool names.
    """
    return ProviderManifest(
        name=name,
        version="1.0.0",
        capabilities=capabilities or _capabilities_for_domains(supported_domains),
        maturity=maturity,
        description=description,
        supported_domains=supported_domains,
        aliases=aliases or [],
        resources=resources
        or [
            f"providers://{name}/catalog",
            f"providers://{name}/health",
        ],
        task_kinds=task_kinds or [],
    )
