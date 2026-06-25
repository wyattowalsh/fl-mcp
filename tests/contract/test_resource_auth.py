"""Contract tests for resource and resource-template auth parity."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest

import fl_mcp.server.factory as factory_module
from fl_mcp.auth.token import check_auth_context
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.server.factory import (
    AUDIO_ANALYSIS_TEMPLATE_URI,
    DOMAIN_CAPABILITIES_TEMPLATE_URI,
    PROJECT_ARRANGEMENT_RESOURCE_URI,
    PROJECT_SNAPSHOT_RESOURCE_URI,
    PROVIDER_MATRIX_RESOURCE_URI,
    RENDER_JOB_TEMPLATE_URI,
    RUNTIME_CAPABILITIES_RESOURCE_URI,
    RUNTIME_HEALTH_RESOURCE_URI,
)


def test_static_resources_require_check_auth_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect_resources() -> dict[str, object | None]:
        resources = await server.list_resources()
        return {str(resource.uri): resource.auth for resource in resources}

    auth_by_uri = asyncio.run(inspect_resources())

    expected_uris = {
        RUNTIME_HEALTH_RESOURCE_URI,
        RUNTIME_CAPABILITIES_RESOURCE_URI,
        PROVIDER_MATRIX_RESOURCE_URI,
        PROJECT_SNAPSHOT_RESOURCE_URI,
        PROJECT_ARRANGEMENT_RESOURCE_URI,
    }
    assert set(auth_by_uri) == expected_uris
    for uri in expected_uris:
        assert auth_by_uri[uri] is check_auth_context, f"{uri} missing auth parity"


def test_resource_templates_require_check_auth_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect_templates() -> dict[str, object | None]:
        templates = await server.list_resource_templates()
        return {
            str(template.uri_template): template.auth for template in templates
        }

    auth_by_template = asyncio.run(inspect_templates())

    expected_templates = {
        DOMAIN_CAPABILITIES_TEMPLATE_URI,
        RENDER_JOB_TEMPLATE_URI,
        AUDIO_ANALYSIS_TEMPLATE_URI,
    }
    assert set(auth_by_template) == expected_templates
    for uri_template in expected_templates:
        assert auth_by_template[uri_template] is check_auth_context, (
            f"{uri_template} missing auth parity"
        )


def test_compact_tools_keep_auth_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect_tools() -> set[object | None]:
        tools = await server.list_tools()
        return {tool.auth for tool in tools}

    tool_auth = asyncio.run(inspect_tools())
    assert tool_auth == {check_auth_context}


def test_resource_auth_matches_tool_auth_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect() -> tuple[object | None, object | None]:
        tool = (await server.list_tools())[0]
        resource = (await server.list_resources())[0]
        return tool.auth, resource.auth

    tool_auth, resource_auth = asyncio.run(inspect())
    assert tool_auth is check_auth_context
    assert resource_auth is check_auth_context
    assert cast(object, tool_auth) is cast(object, resource_auth)