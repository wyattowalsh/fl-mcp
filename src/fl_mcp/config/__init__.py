"""Typed runtime configuration models and settings helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .settings import settings


class Transport(StrEnum):
    """Supported launch transports."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


@dataclass(slots=True, frozen=True)
class RuntimeConfig:
    """Runtime-level metadata used across health and startup logging."""

    environment: str = "dev"
    service_name: str = "fl-mcp"
    service_version: str = "0.1.0"


@dataclass(slots=True, frozen=True)
class StdioConfig:
    """Configuration for stdio transport mode."""

    transport: Transport = Transport.STDIO


@dataclass(slots=True, frozen=True)
class StreamableHTTPConfig:
    """Configuration for streamable HTTP transport mode."""

    transport: Transport = Transport.STREAMABLE_HTTP
    host: str = "127.0.0.1"
    port: int = 8765
    path: str = "/mcp"


@dataclass(slots=True, frozen=True)
class AppConfig:
    """Top-level application config envelope."""

    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    stdio: StdioConfig = field(default_factory=StdioConfig)
    streamable_http: StreamableHTTPConfig = field(default_factory=StreamableHTTPConfig)

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None = None) -> AppConfig:
        """Build typed app config from mapping values."""
        if not values:
            return cls()

        runtime_values = values.get("runtime")
        stdio_values = values.get("stdio")
        http_values = values.get("streamable_http")

        runtime = (
            RuntimeConfig(**runtime_values) if isinstance(runtime_values, dict) else RuntimeConfig()
        )
        stdio = StdioConfig(**stdio_values) if isinstance(stdio_values, dict) else StdioConfig()
        streamable_http = (
            StreamableHTTPConfig(**http_values)
            if isinstance(http_values, dict)
            else StreamableHTTPConfig()
        )
        return cls(runtime=runtime, stdio=stdio, streamable_http=streamable_http)


__all__ = [
    "AppConfig",
    "RuntimeConfig",
    "StdioConfig",
    "StreamableHTTPConfig",
    "Transport",
    "settings",
]
