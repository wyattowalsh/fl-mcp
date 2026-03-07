"""Runtime health surface exposed as MCP resource + tool."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from fl_mcp.config import RuntimeConfig


@dataclass(slots=True, frozen=True)
class RuntimeHealth:
    status: str
    service: str
    version: str
    environment: str
    timestamp: str


def get_runtime_health(config: RuntimeConfig) -> RuntimeHealth:
    return RuntimeHealth(
        status="ok",
        service=config.service_name,
        version=config.service_version,
        environment=config.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def health_payload(config: RuntimeConfig) -> dict[str, str]:
    return asdict(get_runtime_health(config))
