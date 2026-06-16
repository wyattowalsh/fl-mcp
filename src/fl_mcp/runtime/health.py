"""Runtime health surface exposed as MCP resource + tool."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from fl_mcp import __version__
from fl_mcp.config import RuntimeConfig


@dataclass(slots=True, frozen=True)
class RuntimeHealth:
    """Immutable snapshot of runtime health status."""

    status: str = "ok"
    service: str = "fl-mcp"
    version: str = __version__
    environment: str = "dev"
    timestamp: str = ""

    def model_dump(self) -> dict[str, str]:
        """Return a dict compatible with Pydantic-style dumps."""
        return asdict(self)


def get_runtime_health(config: RuntimeConfig) -> RuntimeHealth:
    """Build a RuntimeHealth snapshot from the given configuration.

    Args:
        config: Runtime configuration supplying service identity.

    Returns:
        Frozen health dataclass with current timestamp.
    """
    from fl_mcp.bridge.control_plane import ping
    from fl_mcp.providers.runtime import get_provider_registry

    bridge_health = ping()
    bridge_ok = bridge_health.command_configured if bridge_health.mode == "live" else True

    registry = get_provider_registry(load_entry_points=False)
    provider_statuses = registry.statuses()
    providers_ok = all(s.get("state") != "failed" for s in provider_statuses)

    status = "ok" if (bridge_ok and providers_ok) else "degraded"

    return RuntimeHealth(
        status=status,
        service=config.service_name,
        version=config.service_version,
        environment=config.environment,
        timestamp=datetime.now(UTC).isoformat(),
    )


def health_payload(config: RuntimeConfig) -> dict[str, str]:
    """Return the runtime health snapshot as a plain dictionary.

    Args:
        config: Runtime configuration supplying service identity.

    Returns:
        Health data as a JSON-serializable dict.
    """
    return asdict(get_runtime_health(config))
