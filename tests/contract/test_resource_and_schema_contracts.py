"""Contract tests verifying resource contracts and schema contracts."""

from __future__ import annotations

import json
from typing import get_args

import pytest

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.resources import surface as surface_resources
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
    PluginColorRequest,
    PluginLoadRequest,
    PluginPadInfoRequest,
    PluginParameterRequest,
    PluginParamValueStringRequest,
    PluginReplaceRequest,
    PluginSetParameterRequest,
    PluginSlotRequest,
    PluginWindowRequest,
    ProjectPathRequest,
    RenderExportRequest,
    RenderJobRequest,
    TaskState,
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
from fl_mcp.schemas.transaction import (
    DomainChange,
    RollbackClass,
    TransactionEnvelope,
    TransactionResult,
)

# ---------------------------------------------------------------------------
# Resource contracts
# ---------------------------------------------------------------------------

ALL_RESOURCE_FUNCTIONS = [
    surface_resources.project_snapshot,
    surface_resources.project_arrangement,
    surface_resources.runtime_health,
    surface_resources.runtime_capabilities,
    surface_resources.provider_matrix,
]

TEMPLATE_RESOURCE_FUNCTIONS = [
    lambda: surface_resources.domain_operations("transport"),
    lambda: surface_resources.render_job("test-job-id"),
    lambda: surface_resources.audio_analysis("test-analysis-id"),
]


class TestResourceContracts:
    """Contract 1-7: Resource functions return expected structures."""

    @pytest.mark.parametrize(
        "resource_fn",
        ALL_RESOURCE_FUNCTIONS + TEMPLATE_RESOURCE_FUNCTIONS,
        ids=[
            "project_snapshot",
            "project_arrangement",
            "runtime_health",
            "runtime_capabilities",
            "provider_matrix",
            "domain_operations",
            "render_job",
            "audio_analysis",
        ],
    )
    def test_resource_returns_data_and_resource_keys(self, resource_fn: object) -> None:
        """Contract 1: All 7 resource functions return dicts with 'data' and 'resource' keys."""
        result = resource_fn() if callable(resource_fn) else resource_fn
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "data" in result, f"Missing 'data' key in {result.keys()}"
        assert "resource" in result, f"Missing 'resource' key in {result.keys()}"

    @pytest.mark.parametrize(
        "resource_fn",
        ALL_RESOURCE_FUNCTIONS + TEMPLATE_RESOURCE_FUNCTIONS,
        ids=[
            "project_snapshot",
            "project_arrangement",
            "runtime_health",
            "runtime_capabilities",
            "provider_matrix",
            "domain_operations",
            "render_job",
            "audio_analysis",
        ],
    )
    def test_resource_data_is_json_serializable(self, resource_fn: object) -> None:
        """Contract 2: All resource 'data' values are JSON-serializable."""
        result = resource_fn() if callable(resource_fn) else resource_fn
        data = result["data"]
        # json.dumps should not raise for valid JSON-serializable data
        serialized = json.dumps(data, default=str)
        assert isinstance(serialized, str)

    def test_project_snapshot_data_has_nodes_and_edges(self) -> None:
        """Contract 3: project_snapshot() data has 'nodes' and 'edges' keys."""
        result = surface_resources.project_snapshot()
        data = result["data"]
        # ProjectGraph has nodes and edges; model_dump yields them as dicts
        assert "nodes" in data, f"Missing 'nodes' in snapshot data: {data.keys()}"
        assert "edges" in data, f"Missing 'edges' in snapshot data: {data.keys()}"

    def test_provider_matrix_data_has_provider_name_keys(self) -> None:
        """Contract 4: provider_matrix() data has provider name keys."""
        result = surface_resources.provider_matrix()
        data = result["data"]
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        # Should contain known provider names
        assert len(data) > 0, "Provider matrix should not be empty"
        for key in data:
            assert isinstance(key, str), f"Provider key should be str, got {type(key)}"

    def test_runtime_capabilities_data_has_required_keys(self) -> None:
        """Contract 5: runtime_capabilities() data has 'domains', 'tools', 'providers' keys."""
        result = surface_resources.runtime_capabilities()
        data = result["data"]
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "domains" in data, f"Missing 'domains' in capabilities: {data.keys()}"
        assert "tools" in data, f"Missing 'tools' in capabilities: {data.keys()}"
        assert "providers" in data, f"Missing 'providers' in capabilities: {data.keys()}"

    @pytest.mark.parametrize("domain", list(DOMAINS))
    def test_domain_operations_returns_valid_structure(self, domain: str) -> None:
        """Contract 6: domain_operations for each canonical domain returns valid structure."""
        result = surface_resources.domain_operations(domain)
        assert isinstance(result, dict)
        assert "data" in result
        assert "resource" in result
        data = result["data"]
        assert isinstance(data, dict)
        assert "domain" in data
        # For supported domains, should have tools list; for unsupported, an error key
        assert "tools" in data or "error" in data

    def test_template_render_job_handles_missing_id(self) -> None:
        """Contract 7a: render_job handles missing IDs gracefully."""
        result = surface_resources.render_job("nonexistent-job-id")
        assert isinstance(result, dict)
        assert "data" in result
        assert "resource" in result
        data = result["data"]
        assert isinstance(data, dict)
        assert data.get("message") == "unknown_job" or data.get("state") == "failed"

    def test_template_audio_analysis_handles_missing_id(self) -> None:
        """Contract 7b: audio_analysis handles missing IDs gracefully."""
        result = surface_resources.audio_analysis("nonexistent-analysis-id")
        assert isinstance(result, dict)
        assert "data" in result
        assert "resource" in result
        data = result["data"]
        assert isinstance(data, dict)
        assert data.get("message") == "unknown_analysis" or data.get("state") == "failed"

    def test_template_domain_operations_handles_unknown_domain(self) -> None:
        """Contract 7c: domain_operations handles unknown domains gracefully."""
        result = surface_resources.domain_operations("totally-fake-domain")
        assert isinstance(result, dict)
        assert "data" in result
        data = result["data"]
        assert isinstance(data, dict)
        assert data.get("error") == "unsupported_domain"
        assert "available_domains" in data


# ---------------------------------------------------------------------------
# Schema contracts — FLToolRequest subclasses
# ---------------------------------------------------------------------------

# Classes that have all fields defaulted (can be instantiated with no extra args)
_DEFAULTABLE_REQUEST_CLASSES: list[type[FLToolRequest]] = [
    FLToolRequest,
    EmptyFLToolRequest,
    ConnectionConnectRequest,
    TransportLengthRequest,
    PlaylistArrangementRequest,
    PlaylistClipRequest,
    PlaylistMarkerRequest,
    PlaylistUpdateMarkerRequest,
    PianoRollNotesRequest,
    PianoRollDeleteNotesRequest,
    PianoRollQuantizeRequest,
    PianoRollHumanizeRequest,
    PianoRollGenerateRequest,
    PianoRollGenerateChordRequest,
    PianoRollGenerateMelodyRequest,
    PianoRollGenerateBassRequest,
    RenderExportRequest,
    AudioAnalyzeRequest,
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
    PluginParamValueStringRequest,
    PluginColorRequest,
    PluginPadInfoRequest,
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

# Classes requiring extra args beyond what FLToolRequest base provides
_REQUIRES_ARGS_CLASSES: list[tuple[type[FLToolRequest], dict[str, object]]] = [
    (MidiSendNoteRequest, {"note": 60}),
    (MidiControlChangeRequest, {"control": 1, "value": 64}),
    (MidiProgramChangeRequest, {"program": 0}),
    (MidiPitchBendRequest, {"value": 0}),
    (TransportTempoRequest, {"bpm": 120.0}),
    (TransportPositionRequest, {"position_beats": 0.0}),
    (TransportLoopModeRequest, {"mode": "song"}),
    (TransportPlaybackSpeedRequest, {"speed": 1.0}),
    (MixerTrackRequest, {"track_index": 0}),
    (MixerTrackUpdateRequest, {"track_index": 0}),
    (MixerStereoSeparationRequest, {"track_index": 0, "stereo_separation": 0.0}),
    (ChannelRequest, {"channel_index": 0}),
    (ChannelSelectRequest, {"channel_index": 0}),
    (ChannelUpdateRequest, {"channel_index": 0}),
    (ChannelRouteRequest, {"channel_index": 0, "mixer_track_index": 0}),
    (ChannelStepSequenceRequest, {"channel_index": 0}),
    (ChannelTriggerNoteRequest, {"channel_index": 0, "note": 60}),
    (ChannelPitchRequest, {"channel_index": 0, "pitch": 0.0}),
    (PatternRequest, {"pattern_index": 0}),
    (PatternCreateRequest, {"name": "test"}),
    (PatternRenameRequest, {"pattern_index": 0, "name": "test"}),
    (PatternLengthRequest, {"pattern_index": 0, "length_beats": 4.0}),
    (PlaylistTrackRequest, {"track_index": 0}),
    (PlaylistTrackUpdateRequest, {"track_index": 0, "name": "test"}),
    (
        PlaylistPlaceClipRequest,
        {"source": "test", "start_beats": 0.0, "length_beats": 4.0},
    ),
    (
        PlaylistMoveClipRequest,
        {"destination_track_index": 0, "destination_start_beats": 0.0},
    ),
    (
        PlaylistCreateMarkerRequest,
        {"name": "marker", "position_beats": 0.0},
    ),
    (PianoRollTransposeRequest, {"semitones": 0}),
    (PluginSlotRequest, {"channel_index": 0}),
    (PluginParameterRequest, {"channel_index": 0, "parameter": "gain"}),
    (
        PluginSetParameterRequest,
        {"channel_index": 0, "parameter": "gain", "value": 0.5},
    ),
    (PluginLoadRequest, {"channel_index": 0, "plugin_name": "test"}),
    (
        PluginReplaceRequest,
        {"channel_index": 0, "plugin_name": "test"},
    ),
    (PluginWindowRequest, {"channel_index": 0}),
    (UIWindowRequest, {"window": "mixer"}),
    (UIShowWindowRequest, {"window": "mixer"}),
    (ProjectPathRequest, {"path": "/tmp/test.flp"}),
    (RenderJobRequest, {"job_id": "test-id"}),
    (AudioAnalysisRequest, {"analysis_id": "test-id"}),
]


class TestSchemaContracts:
    """Contract 8-14: Schema models behave correctly."""

    @pytest.mark.parametrize(
        "cls",
        _DEFAULTABLE_REQUEST_CLASSES,
        ids=[c.__name__ for c in _DEFAULTABLE_REQUEST_CLASSES],
    )
    def test_defaultable_request_instantiates_with_no_args(self, cls: type[FLToolRequest]) -> None:
        """Contract 8a: Defaultable FLToolRequest subclasses instantiate with no extra args."""
        instance = cls()
        assert isinstance(instance, FLToolRequest)

    @pytest.mark.parametrize(
        ("cls", "kwargs"),
        _REQUIRES_ARGS_CLASSES,
        ids=[c.__name__ for c, _ in _REQUIRES_ARGS_CLASSES],
    )
    def test_required_arg_request_instantiates_with_minimal_args(
        self, cls: type[FLToolRequest], kwargs: dict[str, object]
    ) -> None:
        """Contract 8b: FLToolRequest subclasses with required fields instantiate with args."""
        instance = cls(**kwargs)
        assert isinstance(instance, FLToolRequest)

    @pytest.mark.parametrize(
        "response_cls,kwargs",
        [
            (
                FLToolExecutionResponse,
                {
                    "tool": "test",
                    "domain": "test",
                    "operation": "test",
                    "status": "ok",
                    "provider": "mock",
                    "bridge_mode": "mock",
                    "message": "ok",
                },
            ),
            (
                FLTaskToolResponse,
                {
                    "tool": "test",
                    "domain": "test",
                    "operation": "test",
                    "status": "ok",
                    "provider": "mock",
                    "bridge_mode": "mock",
                    "message": "ok",
                    "task": {
                        "id": "t1",
                        "state": "queued",
                        "kind": "render",
                    },
                },
            ),
            (
                FLTransactionToolResponse,
                {
                    "tool": "test",
                    "domain": "test",
                    "operation": "test",
                    "status": "planned",
                    "transaction": {},
                },
            ),
        ],
        ids=["FLToolExecutionResponse", "FLTaskToolResponse", "FLTransactionToolResponse"],
    )
    def test_response_models_produce_valid_json(
        self, response_cls: type, kwargs: dict[str, object]
    ) -> None:
        """Contract 9: All response models produce valid JSON via model_dump_json()."""
        instance = response_cls(**kwargs)
        json_str = instance.model_dump_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_transaction_envelope_roundtrip(self) -> None:
        """Contract 10: TransactionEnvelope roundtrips through model_dump() -> model_validate()."""
        envelope = TransactionEnvelope(
            request_id="test-req-001",
            mode="preview",
            changes=[
                DomainChange(
                    domain="mixer",
                    operation="update_track",
                    rollback_class="fully_transactional",
                    payload={"track_index": 0, "volume": 0.8},
                ),
            ],
        )
        dumped = envelope.model_dump()
        restored = TransactionEnvelope.model_validate(dumped)
        assert restored.request_id == envelope.request_id
        assert restored.mode == envelope.mode
        assert len(restored.changes) == len(envelope.changes)
        assert restored.changes[0].domain == "mixer"
        assert restored.model_dump() == dumped

    def test_domain_change_roundtrip(self) -> None:
        """Contract 11: DomainChange roundtrips through model_dump() -> model_validate()."""
        change = DomainChange(
            domain="transport",
            operation="set_tempo",
            rollback_class="checkpointed",
            provider="mock",
            payload={"bpm": 140},
        )
        dumped = change.model_dump()
        restored = DomainChange.model_validate(dumped)
        assert restored.domain == change.domain
        assert restored.operation == change.operation
        assert restored.rollback_class == change.rollback_class
        assert restored.provider == change.provider
        assert restored.payload == change.payload
        assert restored.model_dump() == dumped

    def test_rollback_class_enum_values_are_valid_strings(self) -> None:
        """Contract 12: All RollbackClass enum values are valid strings."""
        rollback_values = get_args(RollbackClass)
        assert len(rollback_values) > 0, "RollbackClass should have values"
        expected = {"fully_transactional", "checkpointed", "best_effort", "unsafe_raw"}
        assert set(rollback_values) == expected
        for value in rollback_values:
            assert isinstance(value, str)
            # Verify each value can be used in a DomainChange
            change = DomainChange(
                domain="test",
                operation="test",
                rollback_class=value,
            )
            assert change.rollback_class == value

    def test_task_state_enum_values_are_valid_strings(self) -> None:
        """Contract 13: All TaskState enum values are valid strings."""
        task_state_values = get_args(TaskState)
        assert len(task_state_values) > 0, "TaskState should have values"
        expected = {"queued", "running", "completed", "canceled", "failed"}
        assert set(task_state_values) == expected
        for value in task_state_values:
            assert isinstance(value, str)

    @pytest.mark.parametrize(
        "model_cls,kwargs",
        [
            (FLToolRequest, {}),
            (EmptyFLToolRequest, {}),
            (TransactionEnvelope, {"request_id": "r1", "mode": "preview", "changes": []}),
            (
                DomainChange,
                {
                    "domain": "test",
                    "operation": "test",
                    "rollback_class": "best_effort",
                },
            ),
            (
                TransactionResult,
                {"transaction_id": "t1", "status": "applied"},
            ),
            (
                FLToolExecutionResponse,
                {
                    "tool": "t",
                    "domain": "d",
                    "operation": "o",
                    "status": "ok",
                    "provider": "mock",
                    "bridge_mode": "mock",
                    "message": "ok",
                },
            ),
            (
                FLTaskInfo,
                {"id": "task1", "state": "queued", "kind": "render"},
            ),
            (
                FLTransactionToolResponse,
                {
                    "tool": "t",
                    "domain": "d",
                    "operation": "o",
                    "status": "planned",
                    "transaction": {},
                },
            ),
        ],
        ids=[
            "FLToolRequest",
            "EmptyFLToolRequest",
            "TransactionEnvelope",
            "DomainChange",
            "TransactionResult",
            "FLToolExecutionResponse",
            "FLTaskInfo",
            "FLTransactionToolResponse",
        ],
    )
    def test_model_json_schema_generation(self, model_cls: type, kwargs: dict[str, object]) -> None:
        """Contract 14: Schema JSON generation (model_json_schema()) works for all models."""
        schema = model_cls.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema or "allOf" in schema or "$defs" in schema
        # Also verify the instance can produce JSON
        instance = model_cls(**kwargs)
        json_str = instance.model_dump_json()
        assert isinstance(json.loads(json_str), dict)
