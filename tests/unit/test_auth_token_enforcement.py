from types import SimpleNamespace

import fl_mcp.auth.token as token_module
from fl_mcp.auth.token import check_auth_context, check_token
from fl_mcp.config.settings import Settings


def test_check_token_respects_optional_setting_and_uses_constant_time_compare(monkeypatch) -> None:
    monkeypatch.setattr(token_module.settings, "auth_token", None)
    assert check_token(None) is True
    assert check_token("anything") is True

    monkeypatch.setattr(token_module.settings, "auth_token", "secret")
    calls: list[tuple[str, str]] = []

    def fake_compare_digest(left: str, right: str) -> bool:
        calls.append((left, right))
        return left == right

    monkeypatch.setattr(token_module.hmac, "compare_digest", fake_compare_digest)

    assert check_token("secret") is True
    assert check_token("wrong") is False
    assert check_token(None) is False
    assert calls == [("secret", "secret"), ("wrong", "secret")]


def test_check_auth_context_supports_multiple_context_shapes(monkeypatch) -> None:
    monkeypatch.setattr(token_module.settings, "auth_token", "secret")

    allowed_contexts = [
        SimpleNamespace(token=SimpleNamespace(token="secret")),
        SimpleNamespace(token="secret"),
        SimpleNamespace(access_token=SimpleNamespace(token="secret")),
        {"token": "secret"},
        {"access_token": {"token": "secret"}},
        "secret",
    ]
    for allowed_context in allowed_contexts:
        assert check_auth_context(allowed_context) is True

    denied_contexts = [
        SimpleNamespace(token=SimpleNamespace(token="other")),
        SimpleNamespace(token=SimpleNamespace(token="")),
        SimpleNamespace(token=None),
        {"token": ""},
        {"token": "secret", "access_token": {"token": "other"}},
        SimpleNamespace(access_token=object()),
        None,
    ]
    for denied_context in denied_contexts:
        assert check_auth_context(denied_context) is False


def test_check_auth_context_denies_ambiguous_tokens_even_without_required_auth(monkeypatch) -> None:
    monkeypatch.setattr(token_module.settings, "auth_token", None)

    assert check_auth_context({"token": "a", "access_token": {"token": "b"}}) is False
    assert check_auth_context(SimpleNamespace(token="  ")) is False
    assert check_auth_context(SimpleNamespace()) is True


def test_settings_treats_empty_env_auth_token_as_unset(monkeypatch) -> None:
    monkeypatch.setenv("FL_MCP_AUTH_TOKEN", "")
    parsed = Settings()
    assert parsed.auth_token is None
