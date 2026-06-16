"""Tests for health degradation paths and planner dict-input guard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fl_mcp.bridge.control_plane import BridgeHealth, ping
from fl_mcp.config import RuntimeConfig
from fl_mcp.runtime.health import get_runtime_health
from fl_mcp.schemas.transaction import DomainChange, TransactionEnvelope
from fl_mcp.transactions.planner import plan_changes


class TestHealthDegradedBridge:
    """get_runtime_health reports degraded when bridge is live without a command."""

    @patch("fl_mcp.providers.runtime.get_provider_registry")
    @patch("fl_mcp.bridge.control_plane.ping")
    def test_health_degraded_when_bridge_live_no_command(
        self,
        mock_ping: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        mock_ping.return_value = BridgeHealth(
            status="degraded",
            mode="live",
            command_configured=False,
        )
        registry = MagicMock()
        registry.statuses.return_value = []
        mock_registry.return_value = registry

        cfg = RuntimeConfig()
        h = get_runtime_health(cfg)
        assert h.status == "degraded"


class TestHealthDegradedProvider:
    """get_runtime_health reports degraded when a provider is in failed state."""

    @patch("fl_mcp.providers.runtime.get_provider_registry")
    @patch("fl_mcp.bridge.control_plane.ping")
    def test_health_degraded_when_provider_failed(
        self,
        mock_ping: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        mock_ping.return_value = BridgeHealth(
            status="ok",
            mode="mock",
            command_configured=False,
        )
        registry = MagicMock()
        registry.statuses.return_value = [
            {"state": "failed", "manifest": {"name": "broken-provider"}},
        ]
        mock_registry.return_value = registry

        cfg = RuntimeConfig()
        h = get_runtime_health(cfg)
        assert h.status == "degraded"


class TestPingDegradedLiveNoCommand:
    """ping() returns degraded status when live mode has no command configured."""

    @patch("fl_mcp.bridge.control_plane.DEFAULT_BRIDGE")
    def test_ping_degraded_when_live_no_command(
        self,
        mock_bridge: MagicMock,
    ) -> None:
        mock_bridge.mode = "live"
        mock_bridge.live_command = None

        result = ping()
        assert isinstance(result, BridgeHealth)
        assert result.status == "degraded"
        assert result.command_configured is False


class TestPlanChangesRawDictInput:
    """plan_changes handles non-envelope input via the getattr guard."""

    def test_plan_changes_raw_dict_input(self) -> None:
        """Calling plan_changes with a proper TransactionEnvelope containing
        a valid change should not raise AttributeError, confirming the
        getattr guard on safety_mode works correctly.
        """
        envelope = TransactionEnvelope(
            request_id="test-raw-001",
            mode="preview",
            changes=[
                DomainChange(
                    domain="mixer",
                    operation="get_track",
                    rollback_class="fully_transactional",
                    payload={"track_index": 0},
                ),
            ],
        )
        result = plan_changes(envelope)
        assert result.status == "planned"
        assert result.transaction_id == "plan-test-raw-001"
        assert len(result.per_domain_results) == 1
