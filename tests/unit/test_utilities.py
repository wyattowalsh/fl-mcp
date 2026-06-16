"""Tests for utility modules: logging, config loading, runtime health, settings."""

from __future__ import annotations

import json
import logging

from fl_mcp.config import RuntimeConfig
from fl_mcp.config.loading import load_config
from fl_mcp.config.settings import Settings
from fl_mcp.logging.setup import JsonFormatter, configure_logging
from fl_mcp.runtime.health import health_payload

# ---------------------------------------------------------------------------
# logging/setup.py — JsonFormatter
# ---------------------------------------------------------------------------


def test_json_formatter_returns_valid_json() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=None,
        exc_info=None,
    )
    formatter = JsonFormatter()
    output = formatter.format(record)
    parsed = json.loads(output)
    assert isinstance(parsed, dict)


def test_json_formatter_contains_required_keys() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="warning message",
        args=None,
        exc_info=None,
    )
    formatter = JsonFormatter()
    parsed = json.loads(formatter.format(record))

    assert "timestamp" in parsed
    assert "level" in parsed
    assert "message" in parsed
    assert parsed["level"] == "WARNING"
    assert parsed["message"] == "warning message"


def test_json_formatter_includes_extra_attributes() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="with extras",
        args=None,
        exc_info=None,
    )
    record.event = "startup"  # type: ignore[attr-defined]
    record.transport = "stdio"  # type: ignore[attr-defined]
    formatter = JsonFormatter()
    parsed = json.loads(formatter.format(record))

    assert parsed["event"] == "startup"
    assert parsed["transport"] == "stdio"


def test_json_formatter_includes_logger_name() -> None:
    record = logging.LogRecord(
        name="my.custom.logger",
        level=logging.DEBUG,
        pathname="test.py",
        lineno=1,
        msg="debug msg",
        args=None,
        exc_info=None,
    )
    formatter = JsonFormatter()
    parsed = json.loads(formatter.format(record))
    assert parsed["logger"] == "my.custom.logger"


# ---------------------------------------------------------------------------
# logging/setup.py — configure_logging()
# ---------------------------------------------------------------------------


def test_configure_logging_does_not_raise() -> None:
    configure_logging()


def test_configure_logging_with_string_level() -> None:
    configure_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_configure_logging_with_int_level() -> None:
    configure_logging(logging.WARNING)
    root = logging.getLogger()
    assert root.level == logging.WARNING


def test_configure_logging_installs_json_formatter() -> None:
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) >= 1
    handler = root.handlers[0]
    assert isinstance(handler.formatter, JsonFormatter)


# ---------------------------------------------------------------------------
# config/loading.py — load_config()
# ---------------------------------------------------------------------------


def test_load_config_empty_returns_empty_dict() -> None:
    result = load_config({})
    assert result == {}


def test_load_config_no_sources_returns_empty_dict() -> None:
    result = load_config()
    assert result == {}


def test_load_config_merges_two_sources() -> None:
    result = load_config({"a": 1}, {"b": 2})
    assert result == {"a": 1, "b": 2}


def test_load_config_later_source_wins() -> None:
    result = load_config({"a": 1}, {"a": 2})
    assert result["a"] == 2


def test_load_config_keys_are_sorted() -> None:
    result = load_config({"z": 3, "a": 1, "m": 2})
    assert list(result.keys()) == ["a", "m", "z"]


def test_load_config_three_sources() -> None:
    result = load_config({"a": 1}, {"b": 2}, {"c": 3})
    assert result == {"a": 1, "b": 2, "c": 3}


# ---------------------------------------------------------------------------
# runtime/health.py — health_payload()
# ---------------------------------------------------------------------------


def test_health_payload_returns_dict_with_expected_keys() -> None:
    config = RuntimeConfig()
    payload = health_payload(config)
    assert isinstance(payload, dict)
    assert "status" in payload
    assert "service" in payload
    assert "version" in payload
    assert "environment" in payload
    assert "timestamp" in payload


def test_health_payload_default_status_is_ok() -> None:
    config = RuntimeConfig()
    payload = health_payload(config)
    assert payload["status"] == "ok"


def test_health_payload_reflects_config_values() -> None:
    config = RuntimeConfig(
        environment="production",
        service_name="custom-svc",
        service_version="1.2.3",
    )
    payload = health_payload(config)
    assert payload["environment"] == "production"
    assert payload["service"] == "custom-svc"
    assert payload["version"] == "1.2.3"


def test_health_payload_is_json_serializable() -> None:
    config = RuntimeConfig()
    payload = health_payload(config)
    serialized = json.dumps(payload)
    assert isinstance(serialized, str)
    roundtrip = json.loads(serialized)
    assert roundtrip == payload


def test_health_payload_timestamp_is_nonempty() -> None:
    config = RuntimeConfig()
    payload = health_payload(config)
    assert payload["timestamp"] != ""


# ---------------------------------------------------------------------------
# config/settings.py — Settings
# ---------------------------------------------------------------------------


def test_settings_has_expected_defaults() -> None:
    s = Settings()
    assert s.app_name == "fl-mcp"
    assert s.log_level == "INFO"
    assert s.http_host == "127.0.0.1"
    assert s.http_port == 8765
    assert s.database_url == "sqlite:///fl_mcp.db"


def test_settings_auth_token_defaults_to_none() -> None:
    s = Settings()
    assert s.auth_token is None


def test_settings_field_types() -> None:
    s = Settings()
    assert isinstance(s.app_name, str)
    assert isinstance(s.log_level, str)
    assert isinstance(s.http_host, str)
    assert isinstance(s.http_port, int)
    assert isinstance(s.database_url, str)
    assert s.auth_token is None or isinstance(s.auth_token, str)


def test_settings_env_prefix() -> None:
    assert Settings.model_config["env_prefix"] == "FL_MCP_"
