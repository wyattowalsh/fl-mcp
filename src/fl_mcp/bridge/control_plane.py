"""Control plane bridge diagnostics."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE


class BridgeHealth(BaseModel):
    """Bridge health payload exposed to diagnostics surfaces."""

    status: str = "ok"
    transport: str = "loopback"
    mode: str = "mock"
    command_configured: bool = False
    domains: list[str] = Field(default_factory=list)


def ping() -> BridgeHealth:
    """Return bridge health metadata for diagnostics surfaces."""

    from fl_mcp.graph.domains import DOMAINS

    return BridgeHealth(
        status="ok",
        transport="subprocess" if DEFAULT_BRIDGE.mode == "live" else "loopback",
        mode=DEFAULT_BRIDGE.mode,
        command_configured=bool(DEFAULT_BRIDGE.live_command),
        domains=list(DOMAINS),
    )
