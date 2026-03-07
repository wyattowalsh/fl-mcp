"""Typed runtime configuration hooks for transport and server startup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Transport(str, Enum):
    """Supported launch transports."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


@dataclass(slots=True, frozen=True)
class RuntimeConfig:
    """Runtime-level options surfaced to health and startup logging."""

    environment: str = "dev"
    service_name: str = "fl-mcp"
    service_version: str = "0.1.0"


@dataclass(slots=True, frozen=True)
class StdioConfig:
    """Configuration for the stdio transport."""

    transport: Transport = Transport.STDIO


@dataclass(slots=True, frozen=True)
class StreamableHTTPConfig:
    """Configuration for streamable HTTP transport."""

    transport: Transport = Transport.STREAMABLE_HTTP
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"


@dataclass(slots=True, frozen=True)
class AppConfig:
    """Top-level app config and typed hook for future settings wiring."""

    runtime: RuntimeConfig = RuntimeConfig()
    stdio: StdioConfig = StdioConfig()
    streamable_http: StreamableHTTPConfig = StreamableHTTPConfig()

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None = None) -> "AppConfig":
        """Build an :class:`AppConfig` from plain settings mappings.

        This is intentionally minimal and acts as a typed integration hook for an upcoming
        settings module.
        """

        if not values:
            return cls()

        runtime_values = values.get("runtime")
        stdio_values = values.get("stdio")
        http_values = values.get("streamable_http")

        runtime = RuntimeConfig(**runtime_values) if isinstance(runtime_values, dict) else RuntimeConfig()
        stdio = StdioConfig(**stdio_values) if isinstance(stdio_values, dict) else StdioConfig()
        streamable_http = (
            StreamableHTTPConfig(**http_values) if isinstance(http_values, dict) else StreamableHTTPConfig()
        )
        return cls(runtime=runtime, stdio=stdio, streamable_http=streamable_http)
