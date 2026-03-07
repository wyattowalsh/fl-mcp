"""FastMCP app factory and registration."""

from __future__ import annotations

from typing import Any

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.logging import configure_logging
from fl_mcp.resources.surface import runtime_health
from fl_mcp.tools import public


class MinimalMCPServer:
    """Fallback server shell when FastMCP runtime is unavailable.

    This keeps local tests and type checks deterministic.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.resources: dict[str, Any] = {"runtime://health": runtime_health}
        self.tools: dict[str, Any] = {
            "query_project": public.query_project,
            "plan_changes": public.plan_changes,
            "apply_changes": public.apply_changes,
            "render_project": public.render_project,
            "analyze_audio": public.analyze_audio,
            "inspect_runtime": public.inspect_runtime,
            "manage_providers": public.manage_providers,
        }


def create_server(name: str = "fl-mcp") -> MinimalMCPServer:
    """Create server object and register core surface."""
    configure_logging()
    _ = ProjectGraph()
    return MinimalMCPServer(name=name)
