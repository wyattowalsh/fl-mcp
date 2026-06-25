"""Contract tests for compact tool metadata synchronization."""

from __future__ import annotations

from fl_mcp.server.factory import COMPACT_TOOL_METADATA, COMPACT_TOOL_NAMES
from fl_mcp.tools import compact
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS

READ_ONLY_COMPACT_TOOLS = {
    "fl_status",
    "fl_snapshot",
    "fl_search_capabilities",
    "fl_get_capability_schema",
    "fl_plan",
}

WRITE_COMPACT_TOOLS = {
    "fl_execute",
    "fl_batch_execute",
    "fl_apply",
    "fl_render",
    "fl_analyze_audio",
    "fl_manage_providers",
    "fl_browser",
}


def _read_only_tools() -> set[str]:
    return {
        name
        for name, metadata in COMPACT_TOOL_METADATA.items()
        if metadata["annotations"]["readOnlyHint"] is True
    }


def _write_tools() -> set[str]:
    return {
        name
        for name, metadata in COMPACT_TOOL_METADATA.items()
        if metadata["annotations"]["readOnlyHint"] is False
    }


def test_compact_tool_metadata_matches_registered_tool_names() -> None:
    assert set(COMPACT_TOOL_METADATA) == set(COMPACT_TOOL_NAMES)
    assert len(COMPACT_TOOL_METADATA) == 12


def test_search_capabilities_description_uses_live_operation_count() -> None:
    description = str(COMPACT_TOOL_METADATA["fl_search_capabilities"]["description"])
    assert f"{len(FL_TOOL_SPECS)}-operation" in description
    assert "216-operation" not in description or len(FL_TOOL_SPECS) == 216


def test_read_only_tools_declare_read_only_hint() -> None:
    assert _read_only_tools() == READ_ONLY_COMPACT_TOOLS
    for name in _read_only_tools():
        annotations = COMPACT_TOOL_METADATA[name]["annotations"]
        assert annotations["readOnlyHint"] is True
        assert annotations.get("destructiveHint") is not True


def test_write_tools_declare_destructive_hint() -> None:
    assert _write_tools() == WRITE_COMPACT_TOOLS
    for name in _write_tools():
        annotations = COMPACT_TOOL_METADATA[name]["annotations"]
        assert annotations["readOnlyHint"] is False
        assert annotations["destructiveHint"] is True


def test_compact_handlers_exist_for_every_metadata_entry() -> None:
    for name in COMPACT_TOOL_NAMES:
        if name == "fl_status":
            assert callable(compact.fl_status)
            continue
        assert callable(getattr(compact, name))