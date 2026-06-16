"""Typed runtime configuration models and settings helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from fl_mcp import __version__

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
    service_version: str = __version__


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

        runtime_values = _mapping_values(values.get("runtime"))
        stdio_values = _mapping_values(values.get("stdio"))
        http_values = _mapping_values(values.get("streamable_http"))

        runtime = RuntimeConfig(**runtime_values) if runtime_values else RuntimeConfig()
        stdio = StdioConfig(**stdio_values) if stdio_values else StdioConfig()
        streamable_http = (
            StreamableHTTPConfig(**http_values) if http_values else StreamableHTTPConfig()
        )
        return cls(runtime=runtime, stdio=stdio, streamable_http=streamable_http)


def _mapping_values(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return cast(dict[str, Any], dict(value))


__all__ = [
    "AppConfig",
    "RuntimeConfig",
    "StdioConfig",
    "StreamableHTTPConfig",
    "Transport",
    "settings",
]
