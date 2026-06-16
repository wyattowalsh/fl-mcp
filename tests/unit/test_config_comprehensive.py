"""Comprehensive tests for configuration loading, settings, and environment variable handling."""

from __future__ import annotations

import dataclasses
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from fl_mcp import __version__
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.loading import load_config
from fl_mcp.config.settings import Settings

# ---------------------------------------------------------------------------
# Settings — default values
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    """Verify Settings() instantiates with expected default values."""

    def test_default_app_name(self) -> None:
        s = Settings()
        assert s.app_name == "fl-mcp"

    def test_default_log_level(self) -> None:
        s = Settings()
        assert s.log_level == "INFO"

    def test_default_auth_token_is_none(self) -> None:
        s = Settings()
        assert s.auth_token is None

    def test_default_http_host(self) -> None:
        s = Settings()
        assert s.http_host == "127.0.0.1"

    def test_default_http_port(self) -> None:
        s = Settings()
        assert s.http_port == 8765

    def test_default_database_url(self) -> None:
        s = Settings()
        assert s.database_url == "sqlite:///fl_mcp.db"


# ---------------------------------------------------------------------------
# Settings — environment variable handling
# ---------------------------------------------------------------------------


class TestSettingsEnvironmentVariables:
    """Verify Settings reads from FL_MCP_ prefixed environment variables."""

    def test_app_name_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_APP_NAME", "custom-app")
        s = Settings()
        assert s.app_name == "custom-app"

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_auth_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_AUTH_TOKEN", "secret-token-123")
        s = Settings()
        assert s.auth_token == "secret-token-123"

    def test_http_host_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_HTTP_HOST", "0.0.0.0")
        s = Settings()
        assert s.http_host == "0.0.0.0"

    def test_http_port_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_HTTP_PORT", "9999")
        s = Settings()
        assert s.http_port == 9999

    def test_database_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FL_MCP_DATABASE_URL", "postgresql://localhost/mydb")
        s = Settings()
        assert s.database_url == "postgresql://localhost/mydb"

    def test_env_var_cleaned_up_after_monkeypatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FL_MCP_APP_NAME", raising=False)
        s = Settings()
        assert s.app_name == "fl-mcp"

    def test_empty_env_var_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """env_ignore_empty=True means empty strings fall back to defaults."""
        monkeypatch.setenv("FL_MCP_APP_NAME", "")
        s = Settings()
        assert s.app_name == "fl-mcp"


# ---------------------------------------------------------------------------
# Settings — port validation
# ---------------------------------------------------------------------------


class TestSettingsPortValidation:
    """Verify http_port validates within 1-65535."""

    def test_port_minimum_valid(self) -> None:
        s = Settings(http_port=1)
        assert s.http_port == 1

    def test_port_maximum_valid(self) -> None:
        s = Settings(http_port=65535)
        assert s.http_port == 65535

    def test_port_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="http_port"):
            Settings(http_port=0)

    def test_port_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="http_port"):
            Settings(http_port=-1)

    def test_port_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="http_port"):
            Settings(http_port=65536)

    def test_port_way_too_high_rejected(self) -> None:
        with pytest.raises(ValidationError, match="http_port"):
            Settings(http_port=100_000)


# ---------------------------------------------------------------------------
# Settings — auth_token
# ---------------------------------------------------------------------------


class TestSettingsAuthToken:
    """Verify auth_token accepts None or string."""

    def test_auth_token_none_by_default(self) -> None:
        s = Settings()
        assert s.auth_token is None

    def test_auth_token_explicit_none(self) -> None:
        s = Settings(auth_token=None)
        assert s.auth_token is None

    def test_auth_token_string_value(self) -> None:
        s = Settings(auth_token="my-secret")
        assert s.auth_token == "my-secret"

    def test_auth_token_empty_string_via_constructor(self) -> None:
        s = Settings(auth_token="")
        assert s.auth_token == ""


# ---------------------------------------------------------------------------
# Settings — model_config and metadata
# ---------------------------------------------------------------------------


class TestSettingsModelConfig:
    """Verify Settings model configuration metadata."""

    def test_env_prefix_is_correct(self) -> None:
        assert Settings.model_config["env_prefix"] == "FL_MCP_"

    def test_env_file_configured(self) -> None:
        assert Settings.model_config["env_file"] == ".env"

    def test_extra_is_ignore(self) -> None:
        assert Settings.model_config["extra"] == "ignore"

    def test_env_ignore_empty_is_true(self) -> None:
        assert Settings.model_config["env_ignore_empty"] is True

    def test_all_fields_have_type_annotations(self) -> None:
        hints = get_type_hints(Settings)
        expected_fields = {
            "app_name",
            "log_level",
            "auth_token",
            "http_host",
            "http_port",
            "database_url",
        }
        for field_name in expected_fields:
            assert field_name in hints, f"Missing type annotation for {field_name}"

    def test_extra_kwargs_ignored(self) -> None:
        """extra='ignore' means unknown fields do not raise."""
        s = Settings(unknown_field="value")  # type: ignore[call-arg]
        assert not hasattr(s, "unknown_field")


# ---------------------------------------------------------------------------
# RuntimeConfig — default construction
# ---------------------------------------------------------------------------


class TestRuntimeConfigDefaults:
    """Verify RuntimeConfig() default construction."""

    def test_default_environment(self) -> None:
        rc = RuntimeConfig()
        assert rc.environment == "dev"

    def test_default_service_name(self) -> None:
        rc = RuntimeConfig()
        assert rc.service_name == "fl-mcp"

    def test_default_service_version(self) -> None:
        rc = RuntimeConfig()
        assert rc.service_version == __version__


# ---------------------------------------------------------------------------
# RuntimeConfig — frozen (immutable)
# ---------------------------------------------------------------------------


class TestRuntimeConfigFrozen:
    """Verify RuntimeConfig is a frozen dataclass."""

    def test_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(RuntimeConfig)

    def test_frozen_environment(self) -> None:
        rc = RuntimeConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rc.environment = "prod"  # type: ignore[misc]

    def test_frozen_service_name(self) -> None:
        rc = RuntimeConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rc.service_name = "other"  # type: ignore[misc]

    def test_frozen_service_version(self) -> None:
        rc = RuntimeConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rc.service_version = "9.9.9"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RuntimeConfig — custom values
# ---------------------------------------------------------------------------


class TestRuntimeConfigCustomValues:
    """Verify RuntimeConfig custom values propagate."""

    def test_custom_environment(self) -> None:
        rc = RuntimeConfig(environment="production")
        assert rc.environment == "production"

    def test_custom_service_name(self) -> None:
        rc = RuntimeConfig(service_name="my-service")
        assert rc.service_name == "my-service"

    def test_custom_service_version(self) -> None:
        rc = RuntimeConfig(service_version="2.0.0")
        assert rc.service_version == "2.0.0"

    def test_all_custom_values(self) -> None:
        rc = RuntimeConfig(
            environment="staging",
            service_name="test-svc",
            service_version="1.2.3",
        )
        assert rc.environment == "staging"
        assert rc.service_name == "test-svc"
        assert rc.service_version == "1.2.3"


# ---------------------------------------------------------------------------
# load_config — no sources
# ---------------------------------------------------------------------------


class TestLoadConfigNoSources:
    """Verify load_config() with no sources returns empty dict."""

    def test_returns_empty_dict(self) -> None:
        result = load_config()
        assert result == {}

    def test_return_type_is_dict(self) -> None:
        result = load_config()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# load_config — merge behavior
# ---------------------------------------------------------------------------


class TestLoadConfigMerge:
    """Verify load_config() merges multiple sources with later-wins semantics."""

    def test_single_source(self) -> None:
        result = load_config({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_later_source_overwrites(self) -> None:
        result = load_config({"key": "first"}, {"key": "second"})
        assert result["key"] == "second"

    def test_merge_disjoint_keys(self) -> None:
        result = load_config({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_three_sources_last_wins(self) -> None:
        result = load_config({"x": 1}, {"x": 2}, {"x": 3})
        assert result["x"] == 3

    def test_mixed_disjoint_and_overlapping(self) -> None:
        result = load_config({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}


# ---------------------------------------------------------------------------
# load_config — deterministic key ordering
# ---------------------------------------------------------------------------


class TestLoadConfigDeterministic:
    """Verify load_config() sorts keys deterministically."""

    def test_keys_are_sorted(self) -> None:
        result = load_config({"z": 1, "a": 2, "m": 3})
        assert list(result.keys()) == ["a", "m", "z"]

    def test_keys_sorted_across_sources(self) -> None:
        result = load_config({"c": 1}, {"a": 2}, {"b": 3})
        assert list(result.keys()) == ["a", "b", "c"]

    def test_deterministic_regardless_of_insertion_order(self) -> None:
        forward = load_config({"z": 1, "a": 2})
        backward = load_config({"a": 2, "z": 1})
        assert forward == backward
        assert list(forward.keys()) == list(backward.keys())


# ---------------------------------------------------------------------------
# load_config — nested dicts
# ---------------------------------------------------------------------------


class TestLoadConfigNestedDicts:
    """Verify load_config() handles nested dicts (shallow merge, not deep)."""

    def test_nested_dict_preserved(self) -> None:
        result = load_config({"outer": {"inner": "value"}})
        assert result == {"outer": {"inner": "value"}}

    def test_nested_dict_overwritten_by_later_source(self) -> None:
        result = load_config(
            {"key": {"a": 1, "b": 2}},
            {"key": {"c": 3}},
        )
        # Shallow merge: later source replaces the entire value
        assert result["key"] == {"c": 3}

    def test_nested_dict_not_deep_merged(self) -> None:
        result = load_config(
            {"settings": {"debug": True, "verbose": False}},
            {"settings": {"debug": False}},
        )
        # The entire nested dict is replaced, not deep-merged
        assert result["settings"] == {"debug": False}


# ---------------------------------------------------------------------------
# load_config — empty sources
# ---------------------------------------------------------------------------


class TestLoadConfigEmptySources:
    """Verify load_config() handles empty sources gracefully."""

    def test_single_empty_source(self) -> None:
        result = load_config({})
        assert result == {}

    def test_multiple_empty_sources(self) -> None:
        result = load_config({}, {}, {})
        assert result == {}

    def test_empty_source_between_real_sources(self) -> None:
        result = load_config({"a": 1}, {}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_empty_source_does_not_clear_previous(self) -> None:
        result = load_config({"key": "value"}, {})
        assert result == {"key": "value"}
