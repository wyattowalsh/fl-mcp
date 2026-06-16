import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pytest

import fl_mcp.server.factory as factory_module
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.server.factory import _build_static_token_auth_provider


def test_build_static_token_auth_provider_returns_none_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    assert _build_static_token_auth_provider() is None


def test_build_static_token_auth_provider_validates_configured_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", "secret")

    @dataclass
    class VerifiedToken:
        token: str

    class FakeVerifier:
        def __init__(self, validate: Callable[[str], bool]) -> None:
            self._validate = validate

        async def verify_token(self, token: str) -> object | None:
            if not self._validate(token):
                return None
            return VerifiedToken(token=token)

    monkeypatch.setattr(factory_module, "_load_debug_token_verifier", lambda: FakeVerifier)
    provider = _build_static_token_auth_provider()
    assert provider is not None

    async def verify_tokens() -> tuple[object | None, object | None]:
        valid = await provider.verify_token("secret")
        invalid = await provider.verify_token("wrong")
        return valid, invalid

    valid, invalid = asyncio.run(verify_tokens())
    assert valid is not None
    assert isinstance(valid, VerifiedToken)
    assert valid.token == "secret"
    assert invalid is None


def test_build_static_token_auth_provider_fails_closed_when_verifier_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", "secret")

    def raise_runtime_error() -> type[object]:
        raise RuntimeError("verifier unavailable")

    monkeypatch.setattr(factory_module, "_load_debug_token_verifier", raise_runtime_error)
    with pytest.raises(RuntimeError, match="verifier unavailable"):
        _build_static_token_auth_provider()


def test_create_server_requires_fastmcp_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    monkeypatch.setattr(factory_module, "_load_fastmcp", lambda: None)

    with pytest.raises(RuntimeError, match="FastMCP runtime is required"):
        factory_module.create_server(RuntimeConfig())


def test_fastmcp_task_tools_register_native_task_metadata() -> None:
    fastmcp_cls = factory_module._load_fastmcp()
    if fastmcp_cls is None or not factory_module._fastmcp_tasks_available(fastmcp_cls):
        pytest.skip("FastMCP task runtime is unavailable")

    server = cast(Any, factory_module.create_server(RuntimeConfig()))

    async def inspect_task_tools() -> None:
        tools = {str(tool.name): tool for tool in await server.list_tools()}

        render = tools["fl_render"]
        audio = tools["fl_analyze_audio"]
        search = tools["fl_search_capabilities"]

        for task_tool in (render, audio):
            assert task_tool.task_config is not None
            assert task_tool.task_config.mode == "optional"
            assert inspect.iscoroutinefunction(task_tool.fn)

        assert search.task_config is not None
        assert search.task_config.mode == "forbidden"
        assert render.output_schema["title"] == "FLTaskEntryResponse"
        assert audio.output_schema["title"] == "FLTaskEntryResponse"
        assert render.annotations.idempotentHint is False
        assert audio.annotations.idempotentHint is False

    asyncio.run(inspect_task_tools())
