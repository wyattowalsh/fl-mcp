"""Schema validation edge-case tests.

Covers TransactionEnvelope, DomainChange, FLToolRequest family,
response models, and RuntimeConfig with both valid and invalid inputs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fl_mcp.config import RuntimeConfig
from fl_mcp.schemas.fl_tools import (
    FLTaskInfo,
    FLTaskToolResponse,
    FLToolExecutionResponse,
    FLToolRequest,
    TransportTempoRequest,
    _FLToolResponseBase,
)
from fl_mcp.schemas.transaction import DomainChange, TransactionEnvelope

# ---------------------------------------------------------------------------
# TransactionEnvelope
# ---------------------------------------------------------------------------


class TestTransactionEnvelope:
    """Edge cases for TransactionEnvelope validation."""

    def test_valid_minimal_envelope(self) -> None:
        env = TransactionEnvelope(request_id="x", mode="preview", changes=[])
        assert env.request_id == "x"
        assert env.mode == "preview"
        assert env.changes == []
        assert env.schema_version == "1.0"
        assert env.execution_policy == "all-or-nothing"

    def test_missing_request_id_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TransactionEnvelope(mode="preview", changes=[])  # type: ignore[call-arg]
        assert "request_id" in str(exc_info.value)

    def test_missing_mode_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TransactionEnvelope(request_id="x", changes=[])  # type: ignore[call-arg]
        assert "mode" in str(exc_info.value)

    def test_missing_changes_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TransactionEnvelope(request_id="x", mode="preview")  # type: ignore[call-arg]
        assert "changes" in str(exc_info.value)

    def test_invalid_mode_value_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TransactionEnvelope(request_id="x", mode="execute", changes=[])  # type: ignore[arg-type]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("mode",) for e in errors)

    def test_safety_mode_accepted_reserved(self) -> None:
        env = TransactionEnvelope(
            request_id="r1",
            mode="apply",
            changes=[],
            safety_mode="relaxed",
        )
        assert env.safety_mode == "relaxed"

    def test_safety_mode_default(self) -> None:
        env = TransactionEnvelope(request_id="r2", mode="preview", changes=[])
        assert env.safety_mode == "standard"

    def test_freshness_policy_accepted_reserved(self) -> None:
        env = TransactionEnvelope(
            request_id="r3",
            mode="preview",
            changes=[],
            freshness_policy="allow-stale",
        )
        assert env.freshness_policy == "allow-stale"

    def test_freshness_policy_default(self) -> None:
        env = TransactionEnvelope(request_id="r4", mode="preview", changes=[])
        assert env.freshness_policy == "strict"

    def test_invalid_safety_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope(
                request_id="x",
                mode="preview",
                changes=[],
                safety_mode="invalid",  # type: ignore[arg-type]
            )

    def test_invalid_freshness_policy_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope(
                request_id="x",
                mode="preview",
                changes=[],
                freshness_policy="maybe",  # type: ignore[arg-type]
            )

    def test_invalid_execution_policy_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope(
                request_id="x",
                mode="preview",
                changes=[],
                execution_policy="best-effort",  # type: ignore[arg-type]
            )

    def test_preconditions_default_empty(self) -> None:
        env = TransactionEnvelope(request_id="x", mode="preview", changes=[])
        assert env.preconditions == []

    def test_metadata_default_empty(self) -> None:
        env = TransactionEnvelope(request_id="x", mode="preview", changes=[])
        assert env.metadata == {}

    def test_target_snapshot_id_optional(self) -> None:
        env = TransactionEnvelope(
            request_id="x",
            mode="preview",
            changes=[],
            target_snapshot_id="snap-123",
        )
        assert env.target_snapshot_id == "snap-123"

    def test_apply_mode_accepted(self) -> None:
        env = TransactionEnvelope(request_id="x", mode="apply", changes=[])
        assert env.mode == "apply"


# ---------------------------------------------------------------------------
# DomainChange
# ---------------------------------------------------------------------------


class TestDomainChange:
    """Edge cases for DomainChange validation."""

    def test_valid_change(self) -> None:
        change = DomainChange(
            domain="mixer",
            operation="set_volume",
            rollback_class="checkpointed",
        )
        assert change.domain == "mixer"
        assert change.operation == "set_volume"
        assert change.rollback_class == "checkpointed"
        assert change.payload == {}
        assert change.provider is None

    def test_missing_domain_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DomainChange(operation="set_volume", rollback_class="checkpointed")  # type: ignore[call-arg]
        assert "domain" in str(exc_info.value)

    def test_missing_operation_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DomainChange(domain="mixer", rollback_class="checkpointed")  # type: ignore[call-arg]
        assert "operation" in str(exc_info.value)

    def test_missing_rollback_class_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DomainChange(domain="mixer", operation="set_volume")  # type: ignore[call-arg]
        assert "rollback_class" in str(exc_info.value)

    def test_invalid_rollback_class_raises(self) -> None:
        with pytest.raises(ValidationError):
            DomainChange(
                domain="mixer",
                operation="set_volume",
                rollback_class="yolo",  # type: ignore[arg-type]
            )

    def test_extra_payload_fields_accepted(self) -> None:
        change = DomainChange(
            domain="channel",
            operation="set_pan",
            rollback_class="fully_transactional",
            payload={"index": 5, "value": 0.7, "nested": {"a": 1}},
        )
        assert change.payload["index"] == 5
        assert change.payload["value"] == 0.7
        assert change.payload["nested"] == {"a": 1}

    def test_provider_optional(self) -> None:
        change = DomainChange(
            domain="mixer",
            operation="mute",
            rollback_class="best_effort",
            provider="flapi",
        )
        assert change.provider == "flapi"

    def test_all_rollback_classes_valid(self) -> None:
        for rc in ("fully_transactional", "checkpointed", "best_effort", "unsafe_raw"):
            change = DomainChange(domain="d", operation="o", rollback_class=rc)  # type: ignore[arg-type]
            assert change.rollback_class == rc


# ---------------------------------------------------------------------------
# FLToolRequest
# ---------------------------------------------------------------------------


class TestFLToolRequest:
    """Edge cases for FLToolRequest and subclasses."""

    def test_base_request_defaults(self) -> None:
        req = FLToolRequest()
        assert req.provider == "auto"
        assert req.session_label is None

    def test_base_request_accepts_provider(self) -> None:
        req = FLToolRequest(provider="mock")
        assert req.provider == "mock"

    def test_base_request_accepts_session_label(self) -> None:
        req = FLToolRequest(session_label="my-session")
        assert req.session_label == "my-session"

    def test_empty_provider_raises(self) -> None:
        with pytest.raises(ValidationError):
            FLToolRequest(provider="")

    def test_custom_provider_name_is_schema_validated_later(self) -> None:
        req = FLToolRequest(provider="studio-custom")
        assert req.provider == "studio-custom"

    def test_transport_tempo_valid(self) -> None:
        req = TransportTempoRequest(bpm=120.0)
        assert req.bpm == 120.0
        assert req.provider == "auto"

    def test_transport_tempo_missing_bpm_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TransportTempoRequest()  # type: ignore[call-arg]
        assert "bpm" in str(exc_info.value)

    def test_transport_tempo_zero_bpm_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransportTempoRequest(bpm=0)

    def test_transport_tempo_negative_bpm_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransportTempoRequest(bpm=-10)

    def test_transport_tempo_exceeds_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            TransportTempoRequest(bpm=401)

    def test_transport_tempo_boundary_max(self) -> None:
        req = TransportTempoRequest(bpm=400)
        assert req.bpm == 400

    def test_transport_tempo_inherits_provider(self) -> None:
        req = TransportTempoRequest(bpm=60, provider="flapi")
        assert req.provider == "flapi"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TestFLToolExecutionResponse:
    """Edge cases for FLToolExecutionResponse."""

    def test_roundtrip_model_validate(self) -> None:
        data = {
            "tool": "transport.set_tempo",
            "domain": "transport",
            "operation": "set_tempo",
            "status": "ok",
            "provider": "mock",
            "bridge_mode": "direct",
            "message": "Tempo set to 120",
        }
        resp = FLToolExecutionResponse.model_validate(data)
        assert resp.tool == "transport.set_tempo"
        assert resp.status == "ok"
        assert resp.result == {}
        assert resp.error_code is None
        assert resp.execution_id is None

    def test_error_status(self) -> None:
        resp = FLToolExecutionResponse(
            tool="mixer.set_volume",
            domain="mixer",
            operation="set_volume",
            status="error",
            provider="flapi",
            bridge_mode="direct",
            message="Connection lost",
            error_code="E_CONN",
        )
        assert resp.status == "error"
        assert resp.error_code == "E_CONN"

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            FLToolExecutionResponse(
                tool="t",
                domain="d",
                operation="o",
                status="pending",  # type: ignore[arg-type]
                provider="p",
                bridge_mode="b",
                message="m",
            )

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            FLToolExecutionResponse(
                tool="t",
                domain="d",
                # missing operation, status, provider, bridge_mode, message
            )  # type: ignore[call-arg]

    def test_result_dict_preserved(self) -> None:
        resp = FLToolExecutionResponse(
            tool="t",
            domain="d",
            operation="o",
            status="ok",
            provider="p",
            bridge_mode="b",
            message="ok",
            result={"tempo": 120, "changed": True},
        )
        assert resp.result["tempo"] == 120
        assert resp.result["changed"] is True


class TestFLTaskToolResponse:
    """Edge cases for FLTaskToolResponse."""

    def test_requires_task_field(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            FLTaskToolResponse(
                tool="render.export",
                domain="render",
                operation="export",
                status="ok",
                provider="mock",
                bridge_mode="async",
                message="started",
                # missing task
            )  # type: ignore[call-arg]
        assert "task" in str(exc_info.value)

    def test_valid_with_task(self) -> None:
        task = FLTaskInfo(id="t1", state="running", kind="render")
        resp = FLTaskToolResponse(
            tool="render.export",
            domain="render",
            operation="export",
            status="ok",
            provider="mock",
            bridge_mode="async",
            message="started",
            task=task,
        )
        assert resp.task.id == "t1"
        assert resp.task.state == "running"
        assert resp.task.progress == 0
        assert resp.task.artifact_uri is None

    def test_task_invalid_state_raises(self) -> None:
        with pytest.raises(ValidationError):
            FLTaskInfo(id="t2", state="unknown", kind="render")  # type: ignore[arg-type]


class TestFLToolResponseBaseInheritance:
    """Verify _FLToolResponseBase fields are inherited correctly."""

    def test_base_fields_present_on_execution_response(self) -> None:
        resp = FLToolExecutionResponse(
            tool="x.y",
            domain="x",
            operation="y",
            status="ok",
            provider="p",
            bridge_mode="b",
            message="m",
        )
        # Fields from _FLToolResponseBase
        assert hasattr(resp, "tool")
        assert hasattr(resp, "domain")
        assert hasattr(resp, "operation")

    def test_base_fields_present_on_task_response(self) -> None:
        task = FLTaskInfo(id="t", state="queued", kind="k")
        resp = FLTaskToolResponse(
            tool="a.b",
            domain="a",
            operation="b",
            status="ok",
            provider="p",
            bridge_mode="b",
            message="m",
            task=task,
        )
        assert resp.tool == "a.b"
        assert resp.domain == "a"
        assert resp.operation == "b"

    def test_base_is_parent_of_execution_response(self) -> None:
        assert issubclass(FLToolExecutionResponse, _FLToolResponseBase)

    def test_base_is_parent_of_task_response(self) -> None:
        assert issubclass(FLTaskToolResponse, _FLToolResponseBase)


# ---------------------------------------------------------------------------
# RuntimeConfig
# ---------------------------------------------------------------------------


class TestRuntimeConfig:
    """Edge cases for RuntimeConfig dataclass."""

    def test_default_construction(self) -> None:
        cfg = RuntimeConfig()
        assert cfg.environment == "dev"
        assert cfg.service_name == "fl-mcp"
        assert isinstance(cfg.service_version, str)
        assert len(cfg.service_version) > 0

    def test_custom_service_name_propagates(self) -> None:
        cfg = RuntimeConfig(service_name="custom-svc")
        assert cfg.service_name == "custom-svc"

    def test_custom_environment(self) -> None:
        cfg = RuntimeConfig(environment="production")
        assert cfg.environment == "production"

    def test_frozen_raises_on_mutation(self) -> None:
        cfg = RuntimeConfig()
        with pytest.raises(AttributeError):
            cfg.service_name = "nope"  # type: ignore[misc]
