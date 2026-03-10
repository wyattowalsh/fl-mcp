"""Compatibility shim for legacy server app import paths."""

from __future__ import annotations

from typing import Any

from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import create_server as _factory_create_server


def create_server(name: str = "fl-mcp") -> Any:
    """Delegate legacy `server.app.create_server` to the canonical factory."""

    runtime_config = RuntimeConfig(service_name=name)
    return _factory_create_server(runtime_config)
