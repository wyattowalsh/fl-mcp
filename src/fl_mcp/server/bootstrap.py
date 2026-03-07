"""Server bootstrap for supported transports."""

from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_TRANSPORTS = {"stdio", "streamable_http"}


@dataclass(frozen=True)
class ServerRuntime:
    transport: str
    started: bool = True


def bootstrap_server(transport: str) -> ServerRuntime:
    if transport not in SUPPORTED_TRANSPORTS:
        msg = f"Unsupported transport: {transport}"
        raise ValueError(msg)
    return ServerRuntime(transport=transport, started=True)
