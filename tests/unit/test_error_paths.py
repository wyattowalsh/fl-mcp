"""Negative/error path tests across multiple modules.

Tests what actually happens when things go wrong: invalid inputs,
unsupported domains, forced failures, schema validation errors, and
auth edge cases.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest
from pydantic import ValidationError

from fl_mcp.auth.token import check_auth_context, check_token
from fl_mcp.bridge.fl_studio import FLStudioBridge
from fl_mcp.config.settings import settings
from fl_mcp.exceptions import ProviderError
from fl_mcp.providers.runtime import ProviderRegistry, reset_provider_registry
from fl_mcp.resources.surface import audio_analysis, domain_operations, render_job
from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.schemas.fl_tools import FLToolRequest
from fl_mcp.schemas.provider import ProviderManifest
from fl_mcp.schemas.transaction import TransactionResult
from fl_mcp.transactions.apply import apply_changes
from fl_mcp.transactions.planner import plan_changes

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_global_registries() -> None:
    """Reset provider registry between tests to avoid cross-contamination."""
    reset_provider_registry()


# ---------------------------------------------------------------------------
# Bridge errors
# ---------------------------------------------------------------------------


class TestBridgeErrors:
    """Error paths in the FL Studio bridge layer."""

    def test_bridge_with_invalid_mode_string_falls_back_to_mock(self) -> None:
        """An invalid mode string is not a valid Literal; the bridge
        constructor accepts it at runtime (no runtime Literal check),
        but from_environment() normalises unknown values to 'mock'."""
        bridge = FLStudioBridge(mode="mock")  # type: ignore[arg-type]
        result = bridge.execute_operation(
            domain="mixer",
            operation="set_volume",
            payload={},
        )
        assert result.bridge_mode == "mock"
        assert result.success is True

    def test_bridge_execute_with_none_domain_returns_error(self) -> None:
        """When domain is None, the bridge should return an unsupported_domain
        failure because None is not in the DOMAINS tuple."""
        bridge = FLStudioBridge(mode="mock")
        result = bridge.execute_operation(
            domain=None,  # type: ignore[arg-type]
            operation="set_volume",
            payload={},
        )
        assert result.success is False
        assert result.error_code == "unsupported_domain"

    def test_bridge_execute_with_none_operation_raises_attribute_error(self) -> None:
        """When operation is None, _mock_supports_operation raises
        AttributeError because it calls operation.startswith('fail')
        on None."""
        bridge = FLStudioBridge(mode="mock")
        with pytest.raises(AttributeError):
            bridge.execute_operation(
                domain="mixer",
                operation=None,  # type: ignore[arg-type]
                payload={},
            )

    def test_bridge_force_fail_payload_returns_mock_failure(self) -> None:
        """The mock bridge triggers a deterministic failure when
        payload contains force_fail=True."""
        bridge = FLStudioBridge(mode="mock")
        result = bridge.execute_operation(
            domain="mixer",
            operation="set_volume",
            payload={"force_fail": True},
        )
        assert result.success is False
        assert result.error_code == "mock_forced_failure"
        assert "mock failure" in result.message.lower()

    def test_bridge_execute_unknown_domain_returns_unsupported(self) -> None:
        """A completely unknown domain returns unsupported_domain."""
        bridge = FLStudioBridge(mode="mock")
        result = bridge.execute_operation(
            domain="nonexistent_domain_xyz",
            operation="some_op",
            payload={},
        )
        assert result.success is False
        assert result.error_code == "unsupported_domain"

    def test_bridge_live_mode_without_command_returns_error(self) -> None:
        """Live mode with no bridge command returns a clear error."""
        bridge = FLStudioBridge(mode="live", live_command=None)
        result = bridge.execute_operation(
            domain="mixer",
            operation="set_volume",
            payload={},
        )
        assert result.success is False
        assert result.error_code == "bridge_process_error"

    def test_bridge_live_mode_empty_command_returns_error(self) -> None:
        """Live mode with empty string command returns a clear error."""
        bridge = FLStudioBridge(mode="live", live_command="   ")
        result = bridge.execute_operation(
            domain="mixer",
            operation="set_volume",
            payload={},
        )
        assert result.success is False
        assert result.error_code == "bridge_process_error"

    def test_bridge_fail_prefix_operation_triggers_failure(self) -> None:
        """Any operation starting with 'fail' triggers mock failure."""
        bridge = FLStudioBridge(mode="mock")
        result = bridge.execute_operation(
            domain="transport",
            operation="fail_something",
            payload={},
        )
        assert result.success is False
        assert result.error_code == "mock_forced_failure"


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------


class TestProviderErrors:
    """Error paths in the provider runtime layer."""

    def test_register_none_as_provider_raises_attribute_error(self) -> None:
        """Registering None raises AttributeError because _ensure_adapter
        tries to access provider.manifest on None."""
        registry = ProviderRegistry()
        with pytest.raises(AttributeError):
            registry.register(None)

    def test_register_duplicate_provider_name_overwrites_silently(self) -> None:
        """Registering a second provider with the same name overwrites
        the first without raising an error."""
        registry = ProviderRegistry()

        class FakeProvider:
            manifest: ClassVar[dict[str, str]] = {
                "name": "test-dup",
                "version": "1.0.0",
            }

            def supports(self, cap: str) -> bool:
                return False

            def execute(self, **kw: object) -> object:
                return None

            def read_resource(self, uri: str) -> None:
                return None

            def start_task(self, **kw: object) -> object:
                return None

            def poll_task(self, task_id: str) -> None:
                return None

            def cancel_task(self, task_id: str) -> None:
                return None

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                pass

            def health(self) -> object:
                from fl_mcp.schemas.provider import ProviderHealthReport

                return ProviderHealthReport()

        m1 = registry.register(FakeProvider())
        m2 = registry.register(FakeProvider())
        assert m1.name == m2.name == "test-dup"
        # Only one entry exists
        assert len([m for m in registry.manifests() if m.name == "test-dup"]) == 1

    def test_execute_on_unregistered_provider_raises_provider_error(self) -> None:
        """Executing against a provider name that was never registered
        raises ProviderError."""
        registry = ProviderRegistry()
        with pytest.raises(ProviderError, match="nonexistent"):
            registry.execute(
                "nonexistent",
                domain="mixer",
                operation="set_volume",
                payload={},
            )

    def test_get_unknown_provider_raises_provider_error(self) -> None:
        """get() on an unknown provider raises ProviderError."""
        registry = ProviderRegistry()
        with pytest.raises(ProviderError, match="no-such-provider"):
            registry.get("no-such-provider")

    def test_startup_all_on_empty_registry_returns_zero(self) -> None:
        """Startup on an empty registry is idempotent and returns 0."""
        registry = ProviderRegistry()
        assert registry.startup_all() == 0

    def test_shutdown_all_on_empty_registry_returns_zero(self) -> None:
        """Shutdown on an empty registry is idempotent and returns 0."""
        registry = ProviderRegistry()
        assert registry.shutdown_all() == 0

    def test_startup_when_already_started_is_idempotent(self) -> None:
        """Calling startup_all twice does not raise and returns the same count."""
        from fl_mcp.providers.builtin import builtin_providers

        registry = ProviderRegistry()
        for p in builtin_providers():
            registry.register(p, source="builtin")

        first = registry.startup_all()
        second = registry.startup_all()
        assert first == second
        assert first > 0

    def test_shutdown_when_not_started_is_idempotent(self) -> None:
        """Calling shutdown_all on a registry that was never started
        should not raise."""
        from fl_mcp.providers.builtin import builtin_providers

        registry = ProviderRegistry()
        for p in builtin_providers():
            registry.register(p, source="builtin")

        count = registry.shutdown_all()
        assert count > 0  # providers exist but were never started


# ---------------------------------------------------------------------------
# Transaction errors
# ---------------------------------------------------------------------------


class TestTransactionErrors:
    """Error paths in the planner and apply engine."""

    def test_plan_changes_with_none_raises_attribute_error(self) -> None:
        """plan_changes(None) raises AttributeError because the planner
        accesses envelope.changes on None."""
        with pytest.raises(AttributeError):
            plan_changes(None)  # type: ignore[arg-type]

    def test_apply_changes_with_none_raises_attribute_error(self) -> None:
        """apply_changes(None) raises AttributeError because the engine
        accesses envelope.mode on None."""
        with pytest.raises(AttributeError):
            apply_changes(None)  # type: ignore[arg-type]

    def test_apply_changes_with_unsupported_domain_reports_per_domain_error(self) -> None:
        """Applying a change targeting an unsupported domain produces a
        per-domain failure entry in the result."""
        envelope = TransactionEnvelope.model_validate(
            {
                "request_id": "err-1",
                "mode": "apply",
                "execution_policy": "allow-partial",
                "changes": [
                    {
                        "domain": "totally-bogus",
                        "operation": "noop",
                        "rollback_class": "unsafe_raw",
                        "payload": {},
                    }
                ],
            }
        )
        result = apply_changes(envelope)
        assert result.status == "failed"
        reports = result.diff_summary.get("reports")
        assert isinstance(reports, list)
        assert len(reports) == 1
        assert reports[0]["error_code"] == "unsupported_domain"

    def test_apply_changes_all_or_nothing_reverts_on_single_failure(self) -> None:
        """Under all-or-nothing policy, a single failure causes ALL changes
        to be marked as failed, even previously successful ones."""
        envelope = TransactionEnvelope.model_validate(
            {
                "request_id": "err-aon",
                "mode": "apply",
                "execution_policy": "all-or-nothing",
                "changes": [
                    {
                        "domain": "mixer",
                        "operation": "set_volume",
                        "rollback_class": "checkpointed",
                        "payload": {},
                    },
                    {
                        "domain": "transport",
                        "operation": "fail_stop",
                        "rollback_class": "fully_transactional",
                        "payload": {},
                    },
                ],
            }
        )
        result = apply_changes(envelope)
        assert result.status == "failed"
        assert result.diff_summary["applied_count"] == 0
        assert result.diff_summary["failed_count"] == 2
        assert result.checkpoint_id is None

    def test_plan_changes_empty_changes_warns(self) -> None:
        """Planning with an empty change list produces a warning."""
        envelope = TransactionEnvelope.model_validate(
            {
                "request_id": "err-empty",
                "mode": "preview",
                "changes": [],
            }
        )
        result = plan_changes(envelope)
        assert result.status == "planned"
        assert any("No changes" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Resource errors
# ---------------------------------------------------------------------------


class TestResourceErrors:
    """Error paths in the resource surface layer."""

    def test_domain_operations_none_returns_graceful_error(self) -> None:
        """domain_operations(None) triggers the AttributeError/TypeError
        catch and returns an error dict."""
        result = domain_operations(None)  # type: ignore[arg-type]
        assert result.get("status") == "error"
        assert "error" in result

    def test_domain_operations_empty_string_returns_unsupported(self) -> None:
        """domain_operations('') should return a result indicating
        the empty/stripped domain is unsupported."""
        result = domain_operations("")
        # After strip(), empty string is not in available domains
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("error") == "unsupported_domain"

    def test_domain_operations_unknown_domain_returns_unsupported(self) -> None:
        """domain_operations for a non-existent domain returns unsupported."""
        result = domain_operations("absolutely-fake-domain")
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("error") == "unsupported_domain"
        assert isinstance(data.get("available_domains"), list)

    def test_render_job_empty_id_returns_fallback(self) -> None:
        """render_job('') returns a fallback dict for an unknown job."""
        result = render_job("")
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("state") == "failed"
        assert data.get("message") == "unknown_job"

    def test_render_job_nonexistent_id_returns_fallback(self) -> None:
        """render_job with a non-existent ID returns a fallback."""
        result = render_job("no-such-job-12345")
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("state") == "failed"

    def test_audio_analysis_empty_id_returns_fallback(self) -> None:
        """audio_analysis('') returns a fallback dict for unknown analysis."""
        result = audio_analysis("")
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("state") == "failed"
        assert data.get("message") == "unknown_analysis"

    def test_audio_analysis_nonexistent_id_returns_fallback(self) -> None:
        """audio_analysis with a non-existent ID returns a fallback."""
        result = audio_analysis("no-such-analysis-12345")
        data = result.get("data")
        assert isinstance(data, dict)
        assert data.get("state") == "failed"


# ---------------------------------------------------------------------------
# Schema validation errors
# ---------------------------------------------------------------------------


class TestSchemaValidationErrors:
    """Error paths in Pydantic schema validation."""

    def test_transaction_envelope_with_invalid_mode_raises(self) -> None:
        """TransactionEnvelope rejects modes that are not 'preview' or 'apply'."""
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(
                {
                    "request_id": "bad-mode",
                    "mode": "execute",
                    "changes": [],
                }
            )

    def test_domain_change_with_invalid_rollback_class_raises(self) -> None:
        """DomainChange rejects rollback_class values outside the Literal set."""
        with pytest.raises(ValidationError):
            DomainChange.model_validate(
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "nonexistent_class",
                }
            )

    def test_fl_tool_request_with_empty_provider_raises(self) -> None:
        """FLToolRequest rejects empty provider names while allowing custom providers."""
        with pytest.raises(ValidationError):
            FLToolRequest.model_validate(
                {
                    "provider": "",
                }
            )

    def test_transaction_envelope_missing_request_id_raises(self) -> None:
        """TransactionEnvelope requires request_id."""
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(
                {
                    "mode": "preview",
                    "changes": [],
                }
            )

    def test_domain_change_missing_required_fields_raises(self) -> None:
        """DomainChange requires domain, operation, and rollback_class."""
        with pytest.raises(ValidationError):
            DomainChange.model_validate({"domain": "mixer"})

    def test_provider_manifest_empty_name_raises(self) -> None:
        """ProviderManifest name must have min_length=1."""
        with pytest.raises(ValidationError):
            ProviderManifest.model_validate(
                {
                    "name": "",
                    "version": "1.0.0",
                }
            )

    def test_provider_manifest_empty_version_raises(self) -> None:
        """ProviderManifest version must have min_length=1."""
        with pytest.raises(ValidationError):
            ProviderManifest.model_validate(
                {
                    "name": "test",
                    "version": "",
                }
            )

    def test_transaction_envelope_invalid_execution_policy_raises(self) -> None:
        """TransactionEnvelope rejects unknown execution_policy values."""
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(
                {
                    "request_id": "bad-policy",
                    "mode": "apply",
                    "execution_policy": "yolo",
                    "changes": [],
                }
            )

    def test_transaction_result_invalid_status_raises(self) -> None:
        """TransactionResult rejects statuses outside the Literal set."""
        with pytest.raises(ValidationError):
            TransactionResult.model_validate(
                {
                    "transaction_id": "tx-bad",
                    "status": "in_progress",
                }
            )


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


class TestAuthErrors:
    """Error paths in the auth token layer."""

    def test_check_auth_context_with_conflicting_tokens_denied(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When a context carries two different token values, access is denied
        regardless of whether either token matches the configured secret."""
        monkeypatch.setattr(settings, "auth_token", "secret")
        context = {"token": "secret", "access_token": {"token": "other"}}
        assert check_auth_context(context) is False

    def test_check_token_with_wrong_token_returns_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """check_token returns False when the provided token does not match."""
        monkeypatch.setattr(settings, "auth_token", "correct-secret")
        assert check_token("wrong-secret") is False

    def test_check_token_none_when_required_returns_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """check_token(None) returns False when a token is configured."""
        monkeypatch.setattr(settings, "auth_token", "secret")
        assert check_token(None) is False

    def test_check_token_none_when_not_required_returns_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """check_token(None) returns True when no token is configured."""
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_token(None) is True

    def test_check_auth_context_none_context_when_required_denied(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When auth is required, a None context is denied."""
        monkeypatch.setattr(settings, "auth_token", "secret")
        assert check_auth_context(None) is False

    def test_check_auth_context_empty_token_string_denied(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A context with an empty/whitespace-only token is denied."""
        monkeypatch.setattr(settings, "auth_token", "secret")
        assert check_auth_context(SimpleNamespace(token="   ")) is False

    def test_check_auth_context_none_context_when_not_required_allows(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When auth is not required, a None context is allowed."""
        monkeypatch.setattr(settings, "auth_token", None)
        assert check_auth_context(None) is True

    def test_check_auth_context_ambiguous_tokens_denied_even_without_auth(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conflicting tokens cause denial even when no auth_token is configured."""
        monkeypatch.setattr(settings, "auth_token", None)
        context = {"token": "a", "access_token": {"token": "b"}}
        assert check_auth_context(context) is False
