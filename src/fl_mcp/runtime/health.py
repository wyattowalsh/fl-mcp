"""Runtime health surface exposed as MCP resource + tool."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from fl_mcp.config import RuntimeConfig


@dataclass(slots=True, frozen=True)
class RuntimeHealth:
    status: str = "ok"
    service: str = "fl-mcp"
    version: str = "0.1.0"
    environment: str = "dev"
    timestamp: str = ""

    def model_dump(self) -> dict[str, str]:
        """Return a dict compatible with Pydantic-style dumps."""
        return asdict(self)


def get_runtime_health(config: RuntimeConfig) -> RuntimeHealth:
    return RuntimeHealth(
        status="ok",
        service=config.service_name,
        version=config.service_version,
        environment=config.environment,
        timestamp=datetime.now(UTC).isoformat(),
    )


def health_payload(config: RuntimeConfig) -> dict[str, str]:
    return asdict(get_runtime_health(config))
