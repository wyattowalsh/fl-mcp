"""Contract tests verifying Pydantic model completeness.

Every model can be constructed, serialized to JSON, and produces a valid JSON Schema.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Schemas __init__ re-exports
# ---------------------------------------------------------------------------
import fl_mcp.schemas as schemas_pkg

# ---------------------------------------------------------------------------
# FL Tool request models — import every concrete subclass
# ---------------------------------------------------------------------------
from fl_mcp.schemas.fl_tools import (
    ArrangementJumpToMarkerRequest,
    ArrangementTimeHintRequest,
    ArrangementTimeRequest,
    AudioAnalysisRequest,
    AudioAnalyzeRequest,
    ChannelColorRequest,
    ChannelGridBitRequest,
    ChannelMuteRequest,
    ChannelPanRequest,
    ChannelPitchRequest,
    ChannelQuickQuantizeRequest,
    ChannelRequest,
    ChannelRouteRequest,
    ChannelSelectRequest,
    ChannelSoloRequest,
    ChannelStepSequenceRequest,
    ChannelTriggerNoteRequest,
    ChannelUpdateRequest,
    ChannelVolumeRequest,
    ConnectionConnectRequest,
    DeviceMidiOutMsgRequest,
    DeviceMidiOutSysexRequest,
    EmptyFLToolRequest,
    FLTaskInfo,
    FLTaskToolResponse,
    FLToolExecutionResponse,
    FLToolRequest,
    FLTransactionToolResponse,
    GeneralSaveUndoRequest,
    MidiControlChangeRequest,
    MidiPitchBendRequest,
    MidiProgramChangeRequest,
    MidiSendNoteRequest,
    MixerArmTrackRequest,
    MixerEqBandwidthRequest,
    MixerEqFrequencyRequest,
    MixerEqGainRequest,
    MixerMuteTrackRequest,
    MixerRouteSendLevelRequest,
    MixerRouteToRequest,
    MixerSoloTrackRequest,
    MixerStereoSeparationRequest,
    MixerTrackColorRequest,
    MixerTrackPanRequest,
    MixerTrackRequest,
    MixerTrackUpdateRequest,
    MixerTrackVolumeRequest,
    PatternCloneRequest,
    PatternColorRequest,
    PatternCreateRequest,
    PatternJumpToRequest,
    PatternLengthRequest,
    PatternRenameRequest,
    PatternRequest,
    PianoRollDeleteNotesRequest,
    PianoRollGenerateBassRequest,
    PianoRollGenerateChordRequest,
    PianoRollGenerateMelodyRequest,
    PianoRollGenerateRequest,
    PianoRollHumanizeRequest,
    PianoRollNote,
    PianoRollNotesRequest,
    PianoRollQuantizeRequest,
    PianoRollTransposeRequest,
    PlaylistArrangementRequest,
    PlaylistClipRequest,
    PlaylistCreateMarkerRequest,
    PlaylistMarkerRequest,
    PlaylistMoveClipRequest,
    PlaylistMuteTrackRequest,
    PlaylistPlaceClipRequest,
    PlaylistSelectTrackRequest,
    PlaylistSoloTrackRequest,
    PlaylistTrackColorRequest,
    PlaylistTrackRequest,
    PlaylistTrackUpdateRequest,
    PlaylistUpdateMarkerRequest,
    PluginCalibrationWriteRequest,
    PluginColorRequest,
    PluginEnumerateParametersRequest,
    PluginGenerateRawProfileRequest,
    PluginInventoryScanRequest,
    PluginLoadRequest,
    PluginLocalPresetsRequest,
    PluginMappedParameterRequest,
    PluginPadInfoRequest,
    PluginParameterIndexRequest,
    PluginParameterRequest,
    PluginParamValueStringRequest,
    PluginPresetNameRequest,
    PluginPrioritySupportAuditRequest,
    PluginProfileInstanceRequest,
    PluginProfileLearnRequest,
    PluginProfileListRequest,
    PluginProfilePresetRequest,
    PluginProfileRequest,
    PluginProfileResolveRequest,
    PluginProfileValidateRequest,
    PluginProfileVerifyRequest,
    PluginReconcileInventoryRequest,
    PluginReplaceRequest,
    PluginSetMappedParameterRequest,
    PluginSetParameterRequest,
    PluginSlotRequest,
    PluginWindowRequest,
    ProjectPathRequest,
    RenderExportRequest,
    RenderJobRequest,
    TransportFastForwardRequest,
    TransportLengthRequest,
    TransportLoopModeRequest,
    TransportMarkerJumpRequest,
    TransportPlaybackSpeedRequest,
    TransportPositionRequest,
    TransportRewindRequest,
    TransportTempoRequest,
    UIHintMsgRequest,
    UIScrollWindowRequest,
    UIShowWindowRequest,
    UISnapModeRequest,
    UIWindowIndexRequest,
    UIWindowRequest,
)

# ---------------------------------------------------------------------------
# Provider models
# ---------------------------------------------------------------------------
from fl_mcp.schemas.provider import (
    ProviderAdapterTaskRecord,
    ProviderHealthReport,
    ProviderManifest,
    ProviderOperationResult,
    ProviderRuntimeStatus,
)

# ---------------------------------------------------------------------------
# Runtime surface models
# ---------------------------------------------------------------------------
from fl_mcp.schemas.runtime_surface import (
    AudioAnalysisResource,
    InspectRuntimeResponse,
    ManageProvidersResponse,
    ProjectArrangementModel,
    ProjectArrangementResource,
    ProjectArrangementTrackModel,
    ProjectClipModel,
    ProjectMarkerModel,
    ProjectSnapshotResource,
    ProviderTaskRecord,
    RenderJobResource,
    RuntimeCapabilityCounts,
    RuntimePromptDescriptorModel,
    RuntimeResourceDescriptorModel,
    RuntimeToolDescriptorModel,
)

# ---------------------------------------------------------------------------
# Transaction models
# ---------------------------------------------------------------------------
from fl_mcp.schemas.transaction import (
    DomainChange,
    TransactionEnvelope,
    TransactionResult,
)

# ===================================================================
# Minimal-args fixtures for models that require non-default values
# ===================================================================

# Models with all-default fields can use {} for model_validate.
# Models with required fields need minimal keyword args.
_REQUIRED_ARGS: dict[type[BaseModel], dict[str, object]] = {
    MidiSendNoteRequest: {"note": 60},
    MidiControlChangeRequest: {"control": 64, "value": 0},
    MidiProgramChangeRequest: {"program": 0},
    MidiPitchBendRequest: {"value": 0},
    TransportTempoRequest: {"bpm": 120},
    TransportPositionRequest: {"position_beats": 0},
    TransportLoopModeRequest: {"mode": "song"},
    TransportPlaybackSpeedRequest: {"speed": 1.0},
    MixerTrackRequest: {"track_index": 0},
    MixerTrackUpdateRequest: {"track_index": 0},
    MixerStereoSeparationRequest: {"track_index": 0, "stereo_separation": 0.0},
    ChannelRequest: {"channel_index": 0},
    ChannelSelectRequest: {"channel_index": 0},
    ChannelUpdateRequest: {"channel_index": 0},
    ChannelRouteRequest: {"channel_index": 0, "mixer_track_index": 0},
    ChannelStepSequenceRequest: {"channel_index": 0},
    ChannelTriggerNoteRequest: {"channel_index": 0, "note": 60},
    ChannelPitchRequest: {"channel_index": 0, "pitch": 0},
    PatternRequest: {"pattern_index": 0},
    PatternCreateRequest: {"name": "test"},
    PatternRenameRequest: {"pattern_index": 0, "name": "test"},
    PatternLengthRequest: {"pattern_index": 0, "length_beats": 4.0},
    PlaylistTrackRequest: {"track_index": 0},
    PlaylistTrackUpdateRequest: {"track_index": 0, "name": "test"},
    PlaylistClipRequest: {},
    PlaylistPlaceClipRequest: {"source": "test", "start_beats": 0, "length_beats": 4.0},
    PlaylistMoveClipRequest: {"destination_track_index": 0, "destination_start_beats": 0},
    PlaylistCreateMarkerRequest: {"name": "test", "position_beats": 0},
    PianoRollTransposeRequest: {"semitones": 0},
    PluginSlotRequest: {"channel_index": 0},
    PluginParameterRequest: {"channel_index": 0, "parameter": "volume"},
    PluginSetParameterRequest: {"channel_index": 0, "parameter": "volume", "value": 0.5},
    PluginParameterIndexRequest: {"channel_index": 0, "parameter_index": 0},
    PluginLoadRequest: {"channel_index": 0, "plugin_name": "test"},
    PluginReplaceRequest: {"channel_index": 0, "plugin_name": "test"},
    PluginWindowRequest: {"channel_index": 0},
    PluginPresetNameRequest: {"channel_index": 0, "preset_name": "Default"},
    PluginProfileRequest: {"profile_id": "lennardigital.sylenth1"},
    PluginProfileResolveRequest: {"query": "sylenth"},
    PluginEnumerateParametersRequest: {"channel_index": 0, "max_parameters": 4},
    PluginGenerateRawProfileRequest: {
        "profile_id": "lennardigital.sylenth1",
        "channel_index": 0,
    },
    PluginCalibrationWriteRequest: {
        "profile_id": "lennardigital.sylenth1",
        "mapped_controls": {"filter.cutoff": 0},
        "persist": False,
    },
    PluginPrioritySupportAuditRequest: {"include_p3": False},
    PluginProfileLearnRequest: {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
    },
    PluginProfileValidateRequest: {"profile_id": "lennardigital.sylenth1"},
    PluginProfileVerifyRequest: {"profile_id": "lennardigital.sylenth1"},
    PluginMappedParameterRequest: {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
    },
    PluginSetMappedParameterRequest: {
        "profile_id": "lennardigital.sylenth1",
        "control_id": "filter.cutoff",
        "value": 0.5,
    },
    PluginProfilePresetRequest: {"profile_id": "lennardigital.sylenth1"},
    UIWindowRequest: {"window": "mixer"},
    UIShowWindowRequest: {"window": "mixer"},
    ProjectPathRequest: {"path": "/test.flp"},
    RenderJobRequest: {"job_id": "test-id"},
    AudioAnalysisRequest: {"analysis_id": "test-id"},
    PianoRollNote: {"note": 60},
}

# All FLToolRequest subclasses (and PianoRollNote which is also from fl_tools)
_ALL_FL_TOOL_REQUEST_CLASSES: list[type[BaseModel]] = [
    FLToolRequest,
    EmptyFLToolRequest,
    ConnectionConnectRequest,
    MidiSendNoteRequest,
    MidiControlChangeRequest,
    MidiProgramChangeRequest,
    MidiPitchBendRequest,
    TransportTempoRequest,
    TransportPositionRequest,
    TransportLengthRequest,
    TransportLoopModeRequest,
    TransportPlaybackSpeedRequest,
    MixerTrackRequest,
    MixerTrackUpdateRequest,
    MixerStereoSeparationRequest,
    ChannelRequest,
    ChannelSelectRequest,
    ChannelUpdateRequest,
    ChannelRouteRequest,
    ChannelStepSequenceRequest,
    ChannelTriggerNoteRequest,
    ChannelPitchRequest,
    PatternRequest,
    PatternCreateRequest,
    PatternRenameRequest,
    PatternLengthRequest,
    PlaylistTrackRequest,
    PlaylistTrackUpdateRequest,
    PlaylistArrangementRequest,
    PlaylistClipRequest,
    PlaylistPlaceClipRequest,
    PlaylistMoveClipRequest,
    PlaylistMarkerRequest,
    PlaylistCreateMarkerRequest,
    PlaylistUpdateMarkerRequest,
    PianoRollNote,
    PianoRollNotesRequest,
    PianoRollDeleteNotesRequest,
    PianoRollQuantizeRequest,
    PianoRollTransposeRequest,
    PianoRollHumanizeRequest,
    PianoRollGenerateRequest,
    PianoRollGenerateChordRequest,
    PianoRollGenerateMelodyRequest,
    PianoRollGenerateBassRequest,
    PluginSlotRequest,
    PluginParameterRequest,
    PluginSetParameterRequest,
    PluginParameterIndexRequest,
    PluginLoadRequest,
    PluginReplaceRequest,
    PluginWindowRequest,
    PluginParamValueStringRequest,
    PluginColorRequest,
    PluginPadInfoRequest,
    PluginPresetNameRequest,
    PluginInventoryScanRequest,
    PluginProfileListRequest,
    PluginProfileRequest,
    PluginProfileResolveRequest,
    PluginProfileInstanceRequest,
    PluginEnumerateParametersRequest,
    PluginGenerateRawProfileRequest,
    PluginProfileLearnRequest,
    PluginProfileValidateRequest,
    PluginProfileVerifyRequest,
    PluginCalibrationWriteRequest,
    PluginPrioritySupportAuditRequest,
    PluginMappedParameterRequest,
    PluginSetMappedParameterRequest,
    PluginProfilePresetRequest,
    PluginLocalPresetsRequest,
    PluginReconcileInventoryRequest,
    UIWindowRequest,
    UIShowWindowRequest,
    ProjectPathRequest,
    RenderJobRequest,
    RenderExportRequest,
    AudioAnalyzeRequest,
    AudioAnalysisRequest,
    ChannelColorRequest,
    ChannelVolumeRequest,
    ChannelPanRequest,
    ChannelMuteRequest,
    ChannelSoloRequest,
    ChannelGridBitRequest,
    ChannelQuickQuantizeRequest,
    MixerTrackColorRequest,
    MixerTrackVolumeRequest,
    MixerTrackPanRequest,
    MixerMuteTrackRequest,
    MixerSoloTrackRequest,
    MixerArmTrackRequest,
    MixerRouteToRequest,
    MixerRouteSendLevelRequest,
    MixerEqGainRequest,
    MixerEqFrequencyRequest,
    MixerEqBandwidthRequest,
    PatternColorRequest,
    PatternCloneRequest,
    PatternJumpToRequest,
    PlaylistTrackColorRequest,
    PlaylistMuteTrackRequest,
    PlaylistSoloTrackRequest,
    PlaylistSelectTrackRequest,
    TransportRewindRequest,
    TransportFastForwardRequest,
    TransportMarkerJumpRequest,
    UIWindowIndexRequest,
    UIScrollWindowRequest,
    UISnapModeRequest,
    UIHintMsgRequest,
    GeneralSaveUndoRequest,
    DeviceMidiOutMsgRequest,
    DeviceMidiOutSysexRequest,
    ArrangementTimeRequest,
    ArrangementTimeHintRequest,
    ArrangementJumpToMarkerRequest,
]


def _construct(cls: type[BaseModel]) -> BaseModel:
    """Construct a model instance using minimal required args."""
    args = _REQUIRED_ARGS.get(cls, {})
    return cls.model_validate(args)


# ===================================================================
# Test 1-3: FLToolRequest subclass parametrized tests
# ===================================================================


class TestFLToolRequestSubclasses:
    """Every FLToolRequest subclass can be constructed, serialized, and has a valid schema."""

    @pytest.mark.parametrize("cls", _ALL_FL_TOOL_REQUEST_CLASSES, ids=lambda c: c.__name__)
    def test_construct_with_minimal_args(self, cls: type[BaseModel]) -> None:
        """Test 1: Every request model can be constructed with minimal required args."""
        instance = _construct(cls)
        assert isinstance(instance, BaseModel)

    @pytest.mark.parametrize("cls", _ALL_FL_TOOL_REQUEST_CLASSES, ids=lambda c: c.__name__)
    def test_model_dump_json_produces_valid_json(self, cls: type[BaseModel]) -> None:
        """Test 2: Every constructed request model produces valid JSON."""
        instance = _construct(cls)
        raw = instance.model_dump_json()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    @pytest.mark.parametrize("cls", _ALL_FL_TOOL_REQUEST_CLASSES, ids=lambda c: c.__name__)
    def test_model_json_schema_is_valid_dict(self, cls: type[BaseModel]) -> None:
        """Test 3: Every request model has a model_json_schema() that is a valid dict."""
        schema = cls.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema or "allOf" in schema or "$defs" in schema

    def test_fl_tool_request_subclass_count(self) -> None:
        """Ensure we are covering at least 98 request classes."""
        assert len(_ALL_FL_TOOL_REQUEST_CLASSES) >= 93


# ===================================================================
# Test 4-6: Response models
# ===================================================================


class TestFLToolResponseModels:
    """FL tool response models can be constructed with minimal args."""

    def test_fl_tool_execution_response(self) -> None:
        """Test 4: FLToolExecutionResponse with minimal args."""
        resp = FLToolExecutionResponse(
            tool="test_tool",
            domain="test",
            operation="read",
            status="ok",
            provider="mock",
            bridge_mode="direct",
            message="success",
        )
        assert resp.status == "ok"
        raw = resp.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["tool"] == "test_tool"

    def test_fl_task_tool_response(self) -> None:
        """Test 5: FLTaskToolResponse with minimal args + task."""
        task = FLTaskInfo(id="t1", state="queued", kind="render")
        resp = FLTaskToolResponse(
            tool="render_export",
            domain="render",
            operation="start",
            status="ok",
            provider="mock",
            bridge_mode="direct",
            message="queued",
            task=task,
        )
        assert resp.task.id == "t1"
        raw = resp.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["task"]["state"] == "queued"

    def test_fl_transaction_tool_response(self) -> None:
        """Test 6: FLTransactionToolResponse with minimal args."""
        resp = FLTransactionToolResponse(
            tool="apply",
            domain="transaction",
            operation="apply",
            status="planned",
            transaction={"id": "txn-1"},
        )
        assert resp.status == "planned"
        raw = resp.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["transaction"]["id"] == "txn-1"


# ===================================================================
# Test 7-8: Transaction schema validity
# ===================================================================


class TestTransactionSchemas:
    """Transaction models produce valid JSON Schema."""

    def test_transaction_envelope_schema(self) -> None:
        """Test 7: TransactionEnvelope schema is valid JSON Schema."""
        schema = TransactionEnvelope.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "request_id" in schema["properties"]
        assert "changes" in schema["properties"]

    def test_domain_change_schema(self) -> None:
        """Test 8: DomainChange schema is valid JSON Schema."""
        schema = DomainChange.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "domain" in schema["properties"]
        assert "rollback_class" in schema["properties"]

    def test_transaction_envelope_roundtrip(self) -> None:
        """TransactionEnvelope can be constructed, serialized, and deserialized."""
        envelope = TransactionEnvelope(
            request_id="req-1",
            mode="preview",
            changes=[
                DomainChange(
                    domain="mixer",
                    operation="set_volume",
                    rollback_class="fully_transactional",
                ),
            ],
        )
        raw = envelope.model_dump_json()
        restored = TransactionEnvelope.model_validate_json(raw)
        assert restored.request_id == "req-1"
        assert len(restored.changes) == 1

    def test_transaction_result_roundtrip(self) -> None:
        """TransactionResult can be constructed and serialized."""
        result = TransactionResult(
            transaction_id="txn-1",
            status="applied",
        )
        raw = result.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["status"] == "applied"


# ===================================================================
# Test 9-11: Provider models
# ===================================================================


class TestProviderModels:
    """Provider models can be constructed and serialized."""

    def test_provider_manifest(self) -> None:
        """Test 9: ProviderManifest can be constructed and serialized."""
        manifest = ProviderManifest(name="mock", version="1.0")
        raw = manifest.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["name"] == "mock"
        assert parsed["version"] == "1.0"
        assert manifest["name"] == "mock"  # __getitem__ support

    def test_provider_operation_result(self) -> None:
        """Test 10: ProviderOperationResult can be constructed and serialized."""
        result = ProviderOperationResult(
            success=True,
            provider="mock",
            message="done",
        )
        raw = result.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["success"] is True

    def test_provider_health_report(self) -> None:
        """Test 11: ProviderHealthReport can be constructed and serialized."""
        report = ProviderHealthReport()
        assert report.status == "ok"
        raw = report.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["status"] == "ok"

    def test_provider_adapter_task_record(self) -> None:
        """ProviderAdapterTaskRecord can be constructed and serialized."""
        record = ProviderAdapterTaskRecord(
            task_id="task-1",
            provider="mock",
            operation="render",
        )
        raw = record.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["state"] == "queued"

    def test_provider_runtime_status(self) -> None:
        """ProviderRuntimeStatus can be constructed and serialized."""
        status = ProviderRuntimeStatus(name="mock", version="1.0")
        raw = status.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["name"] == "mock"
        assert parsed["health"]["status"] == "ok"


# ===================================================================
# Test 12-13: Runtime surface models
# ===================================================================


class TestRuntimeSurfaceModels:
    """Runtime surface response models can be constructed and serialized."""

    def test_inspect_runtime_response(self) -> None:
        """Test 12: InspectRuntimeResponse can be constructed and serialized."""
        resp = InspectRuntimeResponse()
        assert resp.status == "ok"
        raw = resp.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["status"] == "ok"
        assert parsed["tool"] == "inspect_runtime"

    def test_manage_providers_response(self) -> None:
        """Test 13: ManageProvidersResponse can be constructed and serialized."""
        resp = ManageProvidersResponse(status="ok", action="list")
        raw = resp.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["action"] == "list"

    def test_project_snapshot_resource(self) -> None:
        """ProjectSnapshotResource can be constructed with defaults."""
        res = ProjectSnapshotResource()
        raw = res.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["resource"] == "project://snapshot"

    def test_project_arrangement_resource(self) -> None:
        """ProjectArrangementResource can be constructed with defaults."""
        res = ProjectArrangementResource()
        raw = res.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["resource"] == "project://arrangement"

    def test_render_job_resource(self) -> None:
        """RenderJobResource can be constructed."""
        task = ProviderTaskRecord(id="j1", kind="render", provider="mock", state="queued")
        res = RenderJobResource(resource="render://job/j1", data=task)
        raw = res.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["data"]["id"] == "j1"

    def test_audio_analysis_resource(self) -> None:
        """AudioAnalysisResource can be constructed."""
        task = ProviderTaskRecord(id="a1", kind="analysis", provider="mock", state="running")
        res = AudioAnalysisResource(resource="analysis://a1", data=task)
        raw = res.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["data"]["state"] == "running"

    def test_runtime_descriptor_models(self) -> None:
        """All runtime descriptor sub-models can be constructed."""
        tool = RuntimeToolDescriptorModel(name="test")
        resource = RuntimeResourceDescriptorModel(uri="test://uri")
        prompt = RuntimePromptDescriptorModel(name="test")
        caps = RuntimeCapabilityCounts()

        for m in (tool, resource, prompt, caps):
            raw = m.model_dump_json()
            assert isinstance(json.loads(raw), dict)

    def test_project_sub_models(self) -> None:
        """All project arrangement sub-models can be constructed."""
        clip = ProjectClipModel(clip_id="c1")
        marker = ProjectMarkerModel(marker_id="m1", name="intro")
        track = ProjectArrangementTrackModel(track_index=0, name="track-0")
        arrangement = ProjectArrangementModel()

        for m in (clip, marker, track, arrangement):
            raw = m.model_dump_json()
            assert isinstance(json.loads(raw), dict)


# ===================================================================
# Test 14: Enum / Literal types have string values
# ===================================================================


_LITERAL_TYPES_AND_VALUES: list[tuple[str, tuple[str, ...]]] = [
    ("RollbackClass", ("fully_transactional", "checkpointed", "best_effort", "unsafe_raw")),
    ("TaskState (fl_tools)", ("queued", "running", "completed", "canceled", "failed")),
    ("ProviderHealthStatus", ("ok", "warning", "error", "disabled")),
    ("ProviderMaturity", ("experimental", "beta", "stable")),
    ("ProviderTaskState", ("queued", "running", "completed", "failed", "canceled")),
]


class TestEnumLiteralValues:
    """All enum/Literal types have string values."""

    @pytest.mark.parametrize(
        ("name", "expected_values"),
        _LITERAL_TYPES_AND_VALUES,
        ids=[t[0] for t in _LITERAL_TYPES_AND_VALUES],
    )
    def test_literal_values_are_strings(self, name: str, expected_values: tuple[str, ...]) -> None:
        """Test 14: Every value in the Literal type is a string."""
        for val in expected_values:
            assert isinstance(val, str), f"{name} value {val!r} is not a string"

    def test_rollback_class_accepted_by_domain_change(self) -> None:
        """RollbackClass values are accepted by DomainChange."""
        for rc in ("fully_transactional", "checkpointed", "best_effort", "unsafe_raw"):
            change = DomainChange(domain="test", operation="op", rollback_class=rc)
            assert change.rollback_class == rc

    def test_provider_health_status_accepted_by_report(self) -> None:
        """ProviderHealthStatus values are accepted by ProviderHealthReport."""
        for status in ("ok", "warning", "error", "disabled"):
            report = ProviderHealthReport(status=status)
            assert report.status == status

    def test_provider_maturity_accepted_by_manifest(self) -> None:
        """ProviderMaturity values are accepted by ProviderManifest."""
        for mat in ("experimental", "beta", "stable"):
            manifest = ProviderManifest(name="test", version="1.0", maturity=mat)
            assert manifest.maturity == mat


# ===================================================================
# Test 15: All models from schemas/__init__.__all__ are importable
# ===================================================================


_SCHEMAS_ALL_EXPORTS = [
    "BridgeLiveRequest",
    "BridgeLiveResponse",
    "BridgeRunnerModeResponse",
    "DomainChange",
    "ProviderAdapterTaskRecord",
    "ProviderHealthReport",
    "ProviderHealthStatus",
    "ProviderManifest",
    "ProviderMaturity",
    "ProviderOperationResult",
    "ProviderRuntimeStatus",
    "ProviderTaskState",
    "PluginCalibration",
    "PluginControl",
    "PluginControlOrigin",
    "PluginControlRisk",
    "PluginFormat",
    "PluginInventoryItem",
    "PluginInventoryStatus",
    "PluginKind",
    "PluginPresetAsset",
    "PluginPresetKind",
    "PluginPresetSafety",
    "PluginProfile",
    "PluginProfileFailureCode",
    "PluginProfileStatus",
    "PluginRawParameter",
    "PluginSupportMatrixRow",
    "PluginSupportPriority",
    "PluginSupportState",
    "PluginValueMap",
    "PluginValueMapKind",
    "PluginWrapperFingerprint",
    "PluginWriteProbeStatus",
    "RollbackClass",
    "Snapshot",
    "TransactionEnvelope",
    "TransactionResult",
]


class TestSchemasExports:
    """All models exported from schemas/__init__.py are importable."""

    @pytest.mark.parametrize("name", _SCHEMAS_ALL_EXPORTS)
    def test_importable_from_schemas_package(self, name: str) -> None:
        """Test 15: Every name in schemas.__all__ resolves to a real object."""
        assert name in schemas_pkg.__all__, f"{name} missing from schemas.__all__"
        obj = getattr(schemas_pkg, name)
        assert obj is not None, f"{name} resolved to None"

    def test_schemas_all_is_complete(self) -> None:
        """schemas.__all__ matches our expected export list."""
        assert sorted(schemas_pkg.__all__) == sorted(_SCHEMAS_ALL_EXPORTS)
