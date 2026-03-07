"""Diagnostics app shell."""

from fl_mcp.bridge.control_plane import ping
from fl_mcp.resources.surface import runtime_health


def diagnostics_summary() -> dict[str, object]:
    return {
        "runtime": runtime_health(),
        "bridge": ping().model_dump(),
    }
