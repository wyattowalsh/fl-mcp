"""Status and diagnostics contracts shared by CLI and helper app."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class HealthState(StrEnum):
    """Canonical service health values for status endpoints."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


HELPER_STATUS_ENDPOINT = "/v1/helper/status"
HELPER_DIAGNOSTICS_ENDPOINT = "/v1/helper/diagnostics"


@dataclass(slots=True)
class DiagnosticCheck:
    """Single diagnostic check result."""

    name: str
    state: HealthState
    details: str


@dataclass(slots=True)
class HelperStatusPayload:
    """Status payload emitted by CLI diagnostics and consumed by helper app."""

    service: str = "fl-mcp"
    health: HealthState = HealthState.OK
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    endpoint: str = HELPER_STATUS_ENDPOINT
    checks: list[DiagnosticCheck] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to a JSON-serializable dictionary."""

        data = asdict(self)
        data["health"] = self.health.value
        data["checks"] = [{**asdict(check), "state": check.state.value} for check in self.checks]
        return data
