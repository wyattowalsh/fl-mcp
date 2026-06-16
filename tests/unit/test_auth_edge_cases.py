"""Edge-case tests for auth token extraction, normalization, and context handling."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Any

import pytest

from fl_mcp.auth.token import (
    _INVALID_TOKEN,
    _extract_context_token,
    _normalize_token_candidate,
    check_auth_context,
    check_token,
)
from fl_mcp.config.settings import settings

# ---------------------------------------------------------------------------
# _normalize_token_candidate
# ---------------------------------------------------------------------------


class TestNormalizeTokenCandidate:
    """Unit tests for _normalize_token_candidate."""

    def test_string_returns_stripped_string(self) -> None:
        assert _normalize_token_candidate("abc") == "abc"

    def test_string_with_whitespace_is_stripped(self) -> None:
        assert _normalize_token_candidate("  tok  ") == "tok"

    def test_none_returns_none(self) -> None:
        assert _normalize_token_candidate(None) is None

    def test_dict_with_token_key_extracts_value(self) -> None:
        assert _normalize_token_candidate({"token": "secret"}) == "secret"

    def test_dict_without_token_key_returns_invalid(self) -> None:
        assert _normalize_token_candidate({"key": "value"}) is _INVALID_TOKEN

    def test_dict_with_none_token_returns_none(self) -> None:
        assert _normalize_token_candidate({"token": None}) is None

    def test_object_with_token_attr_extracts_value(self) -> None:
        obj = SimpleNamespace(token="my-token")
        assert _normalize_token_candidate(obj) == "my-token"

    def test_object_without_token_attr_returns_invalid(self) -> None:
        obj = SimpleNamespace(name="irrelevant")
        assert _normalize_token_candidate(obj) is _INVALID_TOKEN

    def test_empty_string_returns_invalid(self) -> None:
        assert _normalize_token_candidate("") is _INVALID_TOKEN

    def test_whitespace_only_string_returns_invalid(self) -> None:
        assert _normalize_token_candidate("   ") is _INVALID_TOKEN

    def test_nested_dict_token(self) -> None:
        """Dict whose 'token' value is itself a dict with a 'token' key."""
        assert _normalize_token_candidate({"token": {"token": "deep"}}) == "deep"

    def test_object_with_self_referencing_token_returns_invalid(self) -> None:
        """Guard against infinite recursion when obj.token is obj itself."""
        obj: Any = SimpleNamespace()
        obj.token = obj
        assert _normalize_token_candidate(obj) is _INVALID_TOKEN

    def test_integer_candidate_returns_invalid(self) -> None:
        assert _normalize_token_candidate(42) is _INVALID_TOKEN  # type: ignore[arg-type]

    def test_dict_with_empty_string_token_returns_invalid(self) -> None:
        assert _normalize_token_candidate({"token": ""}) is _INVALID_TOKEN

    def test_dict_with_whitespace_token_returns_invalid(self) -> None:
        assert _normalize_token_candidate({"token": "  "}) is _INVALID_TOKEN


# ---------------------------------------------------------------------------
# _extract_context_token
# ---------------------------------------------------------------------------


class TestExtractContextToken:
    """Unit tests for _extract_context_token."""

    def test_string_context_extracts_token(self) -> None:
        token, deny = _extract_context_token("my-token")
        assert token == "my-token"
        assert deny is False

    def test_dict_context_with_token(self) -> None:
        token, deny = _extract_context_token({"token": "abc"})
        assert token == "abc"
        assert deny is False

    def test_dict_context_without_token_fields(self) -> None:
        token, deny = _extract_context_token({"unrelated": "data"})
        assert token is None
        assert deny is False

    def test_none_context_returns_none_no_deny(self) -> None:
        token, deny = _extract_context_token(None)
        assert token is None
        assert deny is False

    def test_object_with_nested_context_token(self) -> None:
        obj = SimpleNamespace(token=SimpleNamespace(token="nested-secret"))
        token, deny = _extract_context_token(obj)
        assert token == "nested-secret"
        assert deny is False

    def test_dict_with_access_token_field(self) -> None:
        token, deny = _extract_context_token({"access_token": "at-val"})
        assert token == "at-val"
        assert deny is False

    def test_dict_with_auth_token_field(self) -> None:
        token, deny = _extract_context_token({"auth_token": "at-val"})
        assert token == "at-val"
        assert deny is False

    def test_conflicting_tokens_deny(self) -> None:
        token, deny = _extract_context_token({"token": "one", "access_token": "two"})
        assert token is None
        assert deny is True

    def test_consistent_duplicate_tokens_no_deny(self) -> None:
        token, deny = _extract_context_token({"token": "same", "access_token": "same"})
        assert token == "same"
        assert deny is False

    def test_invalid_token_in_source_sets_deny(self) -> None:
        _token, deny = _extract_context_token({"token": ""})
        assert deny is True

    def test_object_with_access_token_attr(self) -> None:
        obj = SimpleNamespace(access_token="at-secret")
        token, deny = _extract_context_token(obj)
        assert token == "at-secret"
        assert deny is False

    def test_empty_dict_context(self) -> None:
        token, deny = _extract_context_token({})
        assert token is None
        assert deny is False


# ---------------------------------------------------------------------------
# check_auth_context — no auth_token configured (no-op)
# ---------------------------------------------------------------------------


class TestCheckAuthContextNoAuth:
    """When settings.auth_token is None, check_auth_context should pass."""

    def test_none_context_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context(None) is True

    def test_string_context_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context("any-token") is True

    def test_dict_context_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context({"token": "anything"}) is True

    def test_empty_namespace_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context(SimpleNamespace()) is True

    def test_ambiguous_tokens_still_denied_without_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ambiguous/invalid token state causes deny even without configured auth."""
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context({"token": "a", "access_token": "b"}) is False


# ---------------------------------------------------------------------------
# check_auth_context — valid token in various shapes
# ---------------------------------------------------------------------------


class TestCheckAuthContextWithAuth:
    """When settings.auth_token is set, verify different valid context shapes."""

    @pytest.fixture(autouse=True)
    def _configure_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", "valid-secret")

    def test_string_context(self) -> None:
        assert check_auth_context("valid-secret") is True

    def test_dict_token_key(self) -> None:
        assert check_auth_context({"token": "valid-secret"}) is True

    def test_dict_access_token_key(self) -> None:
        assert check_auth_context({"access_token": "valid-secret"}) is True

    def test_dict_auth_token_key(self) -> None:
        assert check_auth_context({"auth_token": "valid-secret"}) is True

    def test_namespace_token_attr(self) -> None:
        assert check_auth_context(SimpleNamespace(token="valid-secret")) is True

    def test_namespace_nested_token(self) -> None:
        ctx = SimpleNamespace(token=SimpleNamespace(token="valid-secret"))
        assert check_auth_context(ctx) is True

    def test_wrong_token_denied(self) -> None:
        assert check_auth_context("wrong") is False

    def test_none_context_denied(self) -> None:
        assert check_auth_context(None) is False


# ---------------------------------------------------------------------------
# Custom Mapping subclass
# ---------------------------------------------------------------------------


class _CustomMapping(Mapping[str, Any]):
    """Minimal custom Mapping implementation for testing."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)


class TestTokenFromCustomMapping:
    """Verify that custom Mapping subclasses work with normalization and extraction."""

    def test_normalize_custom_mapping_with_token(self) -> None:
        m = _CustomMapping({"token": "custom-tok"})
        assert _normalize_token_candidate(m) == "custom-tok"

    def test_normalize_custom_mapping_without_token(self) -> None:
        m = _CustomMapping({"other": "val"})
        assert _normalize_token_candidate(m) is _INVALID_TOKEN

    def test_extract_from_custom_mapping(self) -> None:
        m = _CustomMapping({"token": "abc123"})
        token, deny = _extract_context_token(m)
        assert token == "abc123"
        assert deny is False

    def test_check_auth_context_custom_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", "abc123")
        m = _CustomMapping({"token": "abc123"})
        assert check_auth_context(m) is True

    def test_custom_mapping_nested_token(self) -> None:
        m = _CustomMapping({"token": {"token": "nested-val"}})
        assert _normalize_token_candidate(m) == "nested-val"


# ---------------------------------------------------------------------------
# Empty string token
# ---------------------------------------------------------------------------


class TestEmptyStringToken:
    """Verify behavior when token value is an empty string."""

    def test_check_token_empty_string_with_no_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        # No auth configured: empty string still passes (check_token returns True)
        assert check_token("") is True

    def test_check_token_empty_string_with_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_token", "secret")
        assert check_token("") is False

    def test_normalize_empty_string(self) -> None:
        assert _normalize_token_candidate("") is _INVALID_TOKEN

    def test_extract_context_empty_string(self) -> None:
        """A bare empty-string context: treated as source, normalized to INVALID, denied."""
        _token, deny = _extract_context_token("")
        assert deny is True

    def test_check_auth_context_empty_string_with_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "auth_token", "secret")
        assert check_auth_context("") is False

    def test_check_auth_context_empty_string_without_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "auth_token", None)
        # Empty string context yields invalid token → deny=True → False
        assert check_auth_context("") is False
