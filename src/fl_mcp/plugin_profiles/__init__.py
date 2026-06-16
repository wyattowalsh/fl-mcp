"""Plugin-profile registry and operation helpers for FL MCP."""

from fl_mcp.plugin_profiles.inventory import scan_plugin_inventory, scan_preset_assets
from fl_mcp.plugin_profiles.operations import (
    PROFILE_OPERATION_IDS,
    PROFILE_OPERATIONS,
    is_plugin_profile_operation,
    make_plugin_profile_handler,
)
from fl_mcp.plugin_profiles.registry import (
    get_plugin_profile_registry,
    reset_plugin_profile_registry,
)

__all__ = [
    "PROFILE_OPERATIONS",
    "PROFILE_OPERATION_IDS",
    "get_plugin_profile_registry",
    "is_plugin_profile_operation",
    "make_plugin_profile_handler",
    "reset_plugin_profile_registry",
    "scan_plugin_inventory",
    "scan_preset_assets",
]
