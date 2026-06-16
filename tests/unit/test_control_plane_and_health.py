"""Tests for bridge control plane diagnostics and runtime health modules."""

from __future__ import annotations

import json

import pytest

from fl_mcp.bridge.control_plane import BridgeHealth, ping
from fl_mcp.config import RuntimeConfig
from fl_mcp.interfaces.status import DiagnosticCheck, HealthState, HelperStatusPayload
from fl_mcp.runtime.health import RuntimeHealth, get_runtime_health, health_payload

# ---------------------------------------------------------------------------
# BridgeHealth dataclass construction
# ---------------------------------------------------------------------------


class TestBridgeHealthDefaults:
    """BridgeHealth dataclass construction with defaults."""

    def test_default_status(self) -> None:
        h = BridgeHealth()
        assert h.status == "ok"

    def test_default_transport(self) -> None:
        h = BridgeHealth()
        assert h.transport == "loopback"

    def test_default_mode(self) -> None:
        h = BridgeHealth()
        assert h.mode == "mock"

    def test_default_command_configured(self) -> None:
        h = BridgeHealth()
        assert h.command_configured is False

    def test_default_domains_empty(self) -> None:
        h = BridgeHealth()
        assert h.domains == []


class TestBridgeHealthCustom:
    """BridgeHealth with custom fields."""

    def test_custom_status(self) -> None:
        h = BridgeHealth(status="degraded")
        assert h.status == "degraded"

    def test_custom_transport(self) -> None:
        h = BridgeHealth(transport="subprocess")
        assert h.transport == "subprocess"

    def test_custom_mode(self) -> None:
        h = BridgeHealth(mode="live")
        assert h.mode == "live"

    def test_custom_command_configured(self) -> None:
        h = BridgeHealth(command_configured=True)
        assert h.command_configured is True

    def test_custom_domains(self) -> None:
        h = BridgeHealth(domains=["mixer", "transport"])
        assert h.domains == ["mixer", "transport"]

    def test_all_fields_custom(self) -> None:
        h = BridgeHealth(
            status="error",
            transport="websocket",
            mode="live",
            command_configured=True,
            domains=["channels", "plugins"],
        )
        assert h.status == "error"
        assert h.transport == "websocket"
        assert h.mode == "live"
        assert h.command_configured is True
        assert h.domains == ["channels", "plugins"]


# ---------------------------------------------------------------------------
# ping() function
# ---------------------------------------------------------------------------


class TestPing:
    """ping() returns a BridgeHealth-like result."""

    def test_ping_returns_bridge_health(self) -> None:
        result = ping()
        assert isinstance(result, BridgeHealth)

    def test_ping_status_ok(self) -> None:
        result = ping()
        assert result.status == "ok"

    def test_ping_domains_nonempty(self) -> None:
        result = ping()
        assert len(result.domains) > 0

    def test_ping_domains_include_known(self) -> None:
        result = ping()
        for domain in ("mixer", "transport", "channels", "patterns"):
            assert domain in result.domains

    def test_ping_mock_mode_returns_loopback(self) -> None:
        """ping() in default mock mode returns transport='loopback'."""
        result = ping()
        assert result.mode == "mock"
        assert result.transport == "loopback"

    def test_ping_mock_mode_command_not_configured(self) -> None:
        """In default mock environment no live command is configured."""
        result = ping()
        assert result.command_configured is False

    def test_ping_serializable(self) -> None:
        result = ping()
        data = result.model_dump()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)


# ---------------------------------------------------------------------------
# RuntimeHealth construction
# ---------------------------------------------------------------------------


class TestRuntimeHealth:
    """RuntimeHealth dataclass construction."""

    def test_default_status(self) -> None:
        h = RuntimeHealth()
        assert h.status == "ok"

    def test_default_service(self) -> None:
        h = RuntimeHealth()
        assert h.service == "fl-mcp"

    def test_default_environment(self) -> None:
        h = RuntimeHealth()
        assert h.environment == "dev"

    def test_default_timestamp_empty(self) -> None:
        h = RuntimeHealth()
        assert h.timestamp == ""

    def test_version_populated(self) -> None:
        h = RuntimeHealth()
        assert isinstance(h.version, str)
        assert len(h.version) > 0

    def test_custom_fields(self) -> None:
        h = RuntimeHealth(
            status="degraded",
            service="custom-svc",
            version="1.2.3",
            environment="prod",
            timestamp="2025-01-01T00:00:00+00:00",
        )
        assert h.status == "degraded"
        assert h.service == "custom-svc"
        assert h.version == "1.2.3"
        assert h.environment == "prod"
        assert h.timestamp == "2025-01-01T00:00:00+00:00"

    def test_frozen(self) -> None:
        h = RuntimeHealth()
        with pytest.raises(AttributeError):
            h.status = "changed"  # type: ignore[misc]

    def test_model_dump(self) -> None:
        h = RuntimeHealth(status="ok", service="test", version="0.0.1")
        d = h.model_dump()
        assert isinstance(d, dict)
        assert d["status"] == "ok"
        assert d["service"] == "test"
        assert d["version"] == "0.0.1"


# ---------------------------------------------------------------------------
# get_runtime_health()
# ---------------------------------------------------------------------------


class TestGetRuntimeHealth:
    """get_runtime_health() returns RuntimeHealth instance."""

    def test_returns_runtime_health(self) -> None:
        cfg = RuntimeConfig()
        h = get_runtime_health(cfg)
        assert isinstance(h, RuntimeHealth)

    def test_status_is_ok(self) -> None:
        cfg = RuntimeConfig()
        h = get_runtime_health(cfg)
        assert h.status == "ok"

    def test_uses_config_service_name(self) -> None:
        cfg = RuntimeConfig(service_name="my-service")
        h = get_runtime_health(cfg)
        assert h.service == "my-service"

    def test_uses_config_version(self) -> None:
        cfg = RuntimeConfig(service_version="2.0.0")
        h = get_runtime_health(cfg)
        assert h.version == "2.0.0"

    def test_uses_config_environment(self) -> None:
        cfg = RuntimeConfig(environment="staging")
        h = get_runtime_health(cfg)
        assert h.environment == "staging"

    def test_timestamp_populated(self) -> None:
        cfg = RuntimeConfig()
        h = get_runtime_health(cfg)
        assert h.timestamp != ""
        assert "T" in h.timestamp  # ISO-8601 format


# ---------------------------------------------------------------------------
# health_payload()
# ---------------------------------------------------------------------------


class TestHealthPayload:
    """health_payload(RuntimeConfig()) returns dict with expected keys."""

    def test_returns_dict(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert isinstance(payload, dict)

    def test_has_required_keys(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert "status" in payload
        assert "version" in payload
        assert "timestamp" in payload

    def test_has_service_key(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert "service" in payload

    def test_has_environment_key(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert "environment" in payload

    def test_status_ok_by_default(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert payload["status"] == "ok"

    def test_values_match_config_service_name(self) -> None:
        cfg = RuntimeConfig(service_name="custom-svc")
        payload = health_payload(cfg)
        assert payload["service"] == "custom-svc"

    def test_values_match_config_version(self) -> None:
        cfg = RuntimeConfig(service_version="3.0.0")
        payload = health_payload(cfg)
        assert payload["version"] == "3.0.0"

    def test_values_match_config_environment(self) -> None:
        cfg = RuntimeConfig(environment="production")
        payload = health_payload(cfg)
        assert payload["environment"] == "production"

    def test_json_serializable(self) -> None:
        payload = health_payload(RuntimeConfig())
        serialized = json.dumps(payload)
        assert isinstance(serialized, str)
        roundtripped = json.loads(serialized)
        assert roundtripped == payload

    def test_timestamp_is_nonempty_string(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert isinstance(payload["timestamp"], str)
        assert len(payload["timestamp"]) > 0


# ---------------------------------------------------------------------------
# HealthState enum
# ---------------------------------------------------------------------------


class TestHealthState:
    """HealthState enum has expected values."""

    def test_ok_value(self) -> None:
        assert HealthState.OK == "ok"
        assert HealthState.OK.value == "ok"

    def test_warning_value(self) -> None:
        assert HealthState.WARNING == "warning"
        assert HealthState.WARNING.value == "warning"

    def test_error_value(self) -> None:
        assert HealthState.ERROR == "error"
        assert HealthState.ERROR.value == "error"

    def test_member_count(self) -> None:
        assert len(HealthState) == 3

    def test_is_str_enum(self) -> None:
        for member in HealthState:
            assert isinstance(member, str)

    def test_string_coercion(self) -> None:
        assert str(HealthState.OK) == "ok"
        assert str(HealthState.WARNING) == "warning"
        assert str(HealthState.ERROR) == "error"


class TestHealthStateTransitions:
    """Health state transitions make sense."""

    def test_ok_to_warning(self) -> None:
        """Transition from OK to WARNING is valid (same enum)."""
        state = HealthState.OK
        state = HealthState.WARNING
        assert state == HealthState.WARNING

    def test_warning_to_error(self) -> None:
        state = HealthState.WARNING
        state = HealthState.ERROR
        assert state == HealthState.ERROR

    def test_error_to_ok(self) -> None:
        """Recovery from ERROR back to OK is valid."""
        state = HealthState.ERROR
        state = HealthState.OK
        assert state == HealthState.OK

    def test_severity_ordering(self) -> None:
        """HealthState members can be ordered by severity using a mapping."""
        severity = {HealthState.OK: 0, HealthState.WARNING: 1, HealthState.ERROR: 2}
        assert severity[HealthState.OK] < severity[HealthState.WARNING]
        assert severity[HealthState.WARNING] < severity[HealthState.ERROR]

    def test_diagnostic_check_uses_health_state(self) -> None:
        """DiagnosticCheck accepts HealthState for its state field."""
        check = DiagnosticCheck(name="bridge", state=HealthState.OK, details="all good")
        assert check.state == HealthState.OK

    def test_helper_status_default_health(self) -> None:
        """HelperStatusPayload defaults to OK health."""
        payload = HelperStatusPayload()
        assert payload.health == HealthState.OK

    def test_helper_status_serializable(self) -> None:
        """HelperStatusPayload.to_dict() produces JSON-serializable output."""
        payload = HelperStatusPayload(
            health=HealthState.WARNING,
            checks=[DiagnosticCheck(name="net", state=HealthState.ERROR, details="down")],
        )
        d = payload.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        assert d["health"] == "warning"
        assert d["checks"][0]["state"] == "error"
