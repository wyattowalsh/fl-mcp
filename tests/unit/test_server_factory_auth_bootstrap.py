import asyncio
from dataclasses import dataclass

import pytest

import fl_mcp.server.factory as factory_module
from fl_mcp.config import RuntimeConfig
from fl_mcp.server.factory import _build_static_token_auth_provider


def test_build_static_token_auth_provider_returns_none_without_token(monkeypatch) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", None)
    assert _build_static_token_auth_provider() is None


def test_build_static_token_auth_provider_validates_configured_token(monkeypatch) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", "secret")

    @dataclass
    class VerifiedToken:
        token: str

    class FakeVerifier:
        def __init__(self, validate):
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
    monkeypatch,
) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", "secret")

    def raise_runtime_error() -> type[object]:
        raise RuntimeError("verifier unavailable")

    monkeypatch.setattr(factory_module, "_load_debug_token_verifier", raise_runtime_error)
    with pytest.raises(RuntimeError, match="verifier unavailable"):
        _build_static_token_auth_provider()


def test_create_server_fallback_allowed_without_auth(monkeypatch) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", None)
    monkeypatch.setattr(factory_module, "_load_fastmcp", lambda: None)

    server = factory_module.create_server(RuntimeConfig())
    assert isinstance(server, factory_module.MinimalMCPServer)


def test_create_server_fallback_denied_when_auth_required(monkeypatch) -> None:
    monkeypatch.setattr(factory_module.settings, "auth_token", "secret")
    monkeypatch.setattr(factory_module, "_load_fastmcp", lambda: None)

    with pytest.raises(RuntimeError, match="cannot start an unauthenticated fallback server"):
        factory_module.create_server(RuntimeConfig())


def test_minimal_server_query_project_accepts_dict_graph_payload() -> None:
    server = factory_module.MinimalMCPServer(RuntimeConfig())
    response = server.tools["query_project"](
        {"schema_version": "1.0", "nodes": [{"id": "node-1", "kind": "mixer"}], "edges": []},
        "mixer",
    )
    assert response["nodes"][0]["id"] == "node-1"


def test_minimal_server_transaction_handlers_accept_dict_envelopes() -> None:
    server = factory_module.MinimalMCPServer(RuntimeConfig())
    envelope = {
        "request_id": "tx-1",
        "mode": "preview",
        "changes": [{"domain": "mixer", "operation": "noop", "rollback_class": "best_effort"}],
    }
    planned = server.tools["plan_changes"](envelope)
    applied = server.tools["apply_changes"](envelope)

    assert planned["status"] == "planned"
    assert applied["status"] == "planned"
    assert applied["transaction_id"] == "tx-tx-1"
