"""Server bootstrap for supported transports."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_TRANSPORTS = {"stdio", "streamable-http"}
TRANSPORT_ALIASES = {
    "streamable_http": "streamable-http",
}


@dataclass(frozen=True)
class ServerRuntime:
    transport: str
    started: bool = True


def bootstrap_server(transport: str) -> ServerRuntime:
    normalized_transport = TRANSPORT_ALIASES.get(transport, transport)
    if normalized_transport not in SUPPORTED_TRANSPORTS:
        msg = f"Unsupported transport: {transport}"
        raise ValueError(msg)
    return ServerRuntime(transport=normalized_transport, started=True)
