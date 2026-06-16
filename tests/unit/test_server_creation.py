"""Tests for compact FastMCP server creation."""

from __future__ import annotations

import asyncio

from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import (
    AUDIO_ANALYSIS_TEMPLATE_URI,
    COMPACT_SURFACE,
    COMPACT_TOOL_NAMES,
    DOMAIN_CAPABILITIES_TEMPLATE_URI,
    PROJECT_ARRANGEMENT_RESOURCE_URI,
    PROJECT_SNAPSHOT_RESOURCE_URI,
    PROVIDER_MATRIX_RESOURCE_URI,
    RENDER_JOB_TEMPLATE_URI,
    RUNTIME_CAPABILITIES_RESOURCE_URI,
    RUNTIME_HEALTH_RESOURCE_URI,
    create_server,
)


def test_compact_server_creates_fastmcp_instance_with_expected_name() -> None:
    config = RuntimeConfig(service_name="custom-service", environment="production")
    server = create_server(config)

    assert server.name == "custom-service"
    assert server._fl_mcp_surface == COMPACT_SURFACE


def test_compact_server_tools_are_exact_roster() -> None:
    server = create_server(RuntimeConfig())

    async def list_tool_names() -> set[str]:
        return {str(tool.name) for tool in await server.list_tools()}

    assert asyncio.run(list_tool_names()) == set(COMPACT_TOOL_NAMES)


def test_factory_constants_have_expected_values() -> None:
    """Verify resource URI constants match expected patterns."""

    assert RUNTIME_HEALTH_RESOURCE_URI == "runtime://health"
    assert RUNTIME_CAPABILITIES_RESOURCE_URI == "runtime://capabilities"
    assert PROVIDER_MATRIX_RESOURCE_URI == "providers://matrix"
    assert PROJECT_SNAPSHOT_RESOURCE_URI == "project://snapshot"
    assert PROJECT_ARRANGEMENT_RESOURCE_URI == "project://arrangement"
    assert DOMAIN_CAPABILITIES_TEMPLATE_URI == "runtime://capabilities/{domain}"
    assert RENDER_JOB_TEMPLATE_URI == "render://jobs/{job_id}"
    assert AUDIO_ANALYSIS_TEMPLATE_URI == "audio://analyses/{analysis_id}"
