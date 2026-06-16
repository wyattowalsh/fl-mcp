"""Explicit FL Studio tool surface built on a shared operation catalog."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel

from fl_mcp.bridge.fl_studio import (
    DEFAULT_BRIDGE,
    BridgeExecutionResult,
    default_provider_for_operation,
)
from fl_mcp.bridge.live_surface import (
    FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS,
    LIVE_FLAPI_OPERATIONS,
)
from fl_mcp.plugin_profiles.operations import (
    is_plugin_profile_operation,
    make_plugin_profile_handler,
)
from fl_mcp.runtime.state import get_runtime_state
from fl_mcp.schemas import DomainChange, RollbackClass, TransactionEnvelope
from fl_mcp.schemas.fl_tools import (
    ArrangementJumpToMarkerRequest,
    ArrangementTimeHintRequest,
    ArrangementTimeRequest,
    AudioAnalysisRequest,
    AudioAnalyzeRequest,
    AutomationClipRequest,
    AutomationCreateRequest,
    AutomationLinkRequest,
    AutomationWritePointsRequest,
    ChannelColorRequest,
    ChannelGridBitRequest,
    ChannelLoadSampleRequest,
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
    FLTaskToolResponse,
    FLToolExecutionResponse,
    FLToolRequest,
    FLTransactionToolResponse,
    GeneralNewProjectRequest,
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
    MixerSetSlotPluginRequest,
    MixerSlotEnableRequest,
    MixerSlotRequest,
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
    TransportSwingRequest,
    TransportTempoRequest,
    TransportTimeSignatureRequest,
    UIHintMsgRequest,
    UIScrollWindowRequest,
    UIShowWindowRequest,
    UISnapModeRequest,
    UIWindowIndexRequest,
    UIWindowRequest,
)
from fl_mcp.schemas.runtime_surface import ProviderTaskRecord

ToolExecutionMode = Literal["read", "transaction", "direct"]
_NATIVE_FASTMCP_TASK_ID: ContextVar[str | None] = ContextVar(
    "fl_mcp_native_fastmcp_task_id",
    default=None,
)


@contextmanager
def native_task_id_context(task_id: str | None) -> Iterator[None]:
    """Temporarily bind the active FastMCP task ID for repo-owned task records."""
    if task_id is None:
        yield
        return
    token = _NATIVE_FASTMCP_TASK_ID.set(task_id)
    try:
        yield
    finally:
        _NATIVE_FASTMCP_TASK_ID.reset(token)


def _native_task_id() -> str | None:
    return _NATIVE_FASTMCP_TASK_ID.get()


@dataclass(slots=True, frozen=True)
class FLToolSpec:
    """Immutable specification for a single FL Studio tool endpoint."""

    name: str
    description: str
    domain: str
    operation: str
    request_model: type[FLToolRequest]
    response_model: type[BaseModel]
    execution_mode: ToolExecutionMode
    rollback_class: RollbackClass | None
    tags: tuple[str, ...]
    annotations: dict[str, object]
    timeout: float | None = None
    task: bool = False

    def model_dump(self) -> dict[str, object]:
        """Serialize the spec to a plain dict for catalog responses."""
        return {
            "name": self.name,
            "operation_id": f"{self.domain}.{self.operation}",
            "description": self.description,
            "domain": self.domain,
            "operation": self.operation,
            "default_provider": default_provider_for_operation(self.domain, self.operation),
            "request_model": self.request_model.__name__,
            "response_model": self.response_model.__name__,
            "execution_mode": self.execution_mode,
            "rollback_class": self.rollback_class,
            "tags": list(self.tags),
            "annotations": dict(self.annotations),
            "timeout": self.timeout,
            "task": self.task,
        }


def _annotations(
    *,
    read_only: bool,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = True,
) -> dict[str, object]:
    return {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "idempotentHint": idempotent,
        "openWorldHint": open_world,
    }


def _result_progress(value: object) -> float:
    if not isinstance(value, (int, float, str)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


PROVIDER_MATRIX: dict[str, dict[str, object]] = {
    "flapi-live": {
        "description": (
            "Forced-live provider for attempting every compact FL operation through "
            "the bundled FL Studio host-file bridge."
        ),
        "aliases": ["flapi"],
        "supported_domains": list(FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS),
        "supported_operations": {
            domain: list(operations) for domain, operations in LIVE_FLAPI_OPERATIONS.items()
        },
        "capabilities": [],
    },
    "piano-roll-script": {
        "description": (
            "Preferred live provider for persistent piano-roll and pattern-writing flows."
        ),
        "aliases": ["midi-script", "midi-script-live"],
        "supported_domains": ["piano-roll", "patterns"],
        "capabilities": ["piano-roll", "pattern-edit", "composition"],
    },
    "midi-fallback": {
        "description": "Degraded live provider for bounded MIDI and note-injection operations.",
        "aliases": [],
        "supported_domains": ["connection", "midi", "channels", "transport", "device"],
        "capabilities": ["midi", "note-trigger", "transport-fallback"],
    },
    "mock": {
        "description": "Deterministic provider for CI and local development.",
        "supported_domains": [
            "connection",
            "midi",
            "transport",
            "mixer",
            "channels",
            "patterns",
            "playlist",
            "piano-roll",
            "plugins",
            "ui",
            "general",
            "render",
            "audio",
            "device",
            "arrangement",
            "automation",
        ],
        "capabilities": ["all"],
    },
}


def _spec(
    name: str,
    description: str,
    domain: str,
    operation: str,
    request_model: type[FLToolRequest],
    execution_mode: ToolExecutionMode,
    *,
    response_model: type[BaseModel] | None = None,
    rollback_class: RollbackClass | None = None,
    tags: tuple[str, ...],
    annotations: dict[str, object],
    timeout: float | None = None,
    task: bool = False,
) -> FLToolSpec:
    resolved_response_model = response_model
    if resolved_response_model is None:
        if task:
            resolved_response_model = FLTaskToolResponse
        elif execution_mode == "transaction":
            resolved_response_model = FLTransactionToolResponse
        else:
            resolved_response_model = FLToolExecutionResponse
    return FLToolSpec(
        name=name,
        description=description,
        domain=domain,
        operation=operation,
        request_model=request_model,
        response_model=resolved_response_model,
        execution_mode=execution_mode,
        rollback_class=rollback_class,
        tags=tags,
        annotations=annotations,
        timeout=timeout,
        task=task,
    )


FL_TOOL_SPECS: tuple[FLToolSpec, ...] = (
    _spec(
        "connection_status",
        "Inspect the configured FL Studio bridge/provider connection state.",
        "connection",
        "status",
        EmptyFLToolRequest,
        "read",
        tags=("connection", "runtime"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "connection_connect",
        "Configure input/output bridge ports for the current FL Studio session.",
        "connection",
        "connect",
        ConnectionConnectRequest,
        "direct",
        tags=("connection", "runtime"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "midi_list_ports",
        "List available MIDI bridge ports.",
        "midi",
        "list_ports",
        EmptyFLToolRequest,
        "read",
        tags=("midi", "runtime"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "midi_send_note",
        "Send a MIDI note through the configured FL Studio bridge.",
        "midi",
        "send_note",
        MidiSendNoteRequest,
        "direct",
        tags=("midi", "note"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "midi_send_cc",
        "Send a MIDI control-change message through the configured FL Studio bridge.",
        "midi",
        "send_cc",
        MidiControlChangeRequest,
        "direct",
        tags=("midi", "control"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "midi_send_program_change",
        "Send a MIDI program-change message through the configured FL Studio bridge.",
        "midi",
        "send_program_change",
        MidiProgramChangeRequest,
        "direct",
        tags=("midi", "program"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "midi_send_pitch_bend",
        "Send a MIDI pitch-bend message through the configured FL Studio bridge.",
        "midi",
        "send_pitch_bend",
        MidiPitchBendRequest,
        "direct",
        tags=("midi", "pitch"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_get_state",
        "Read current FL Studio transport state.",
        "transport",
        "get_state",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_get_tempo",
        "Read the current project tempo in beats per minute.",
        "transport",
        "get_tempo",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "tempo"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_get_song_position",
        "Read the current song position in beats.",
        "transport",
        "get_song_position",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "position"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_get_length",
        "Read the current song or pattern length in beats.",
        "transport",
        "get_length",
        TransportLengthRequest,
        "read",
        tags=("transport", "length"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_play",
        "Start playback in FL Studio.",
        "transport",
        "play",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "playback"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_pause",
        "Pause playback in FL Studio without rewinding the transport.",
        "transport",
        "pause",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "playback"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_stop",
        "Stop playback in FL Studio.",
        "transport",
        "stop",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "playback"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_record",
        "Toggle recording in FL Studio.",
        "transport",
        "record",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "record"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_set_tempo",
        "Set project tempo in beats per minute.",
        "transport",
        "set_tempo",
        TransportTempoRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("transport", "tempo"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "transport_set_song_position",
        "Set the current song position in beats.",
        "transport",
        "set_song_position",
        TransportPositionRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "position"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "transport_set_loop_mode",
        "Switch between song and pattern loop modes.",
        "transport",
        "set_loop_mode",
        TransportLoopModeRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "loop"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "transport_set_playback_speed",
        "Adjust FL Studio playback speed.",
        "transport",
        "set_playback_speed",
        TransportPlaybackSpeedRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "speed"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    # --- transport domain: granular FL Studio API surface ---
    _spec(
        "transport_rewind",
        "Rewind the transport position.",
        "transport",
        "rewind",
        TransportRewindRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_fast_forward",
        "Fast-forward the transport position.",
        "transport",
        "fast_forward",
        TransportFastForwardRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_is_recording",
        "Check whether FL Studio is currently recording.",
        "transport",
        "is_recording",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "state"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "transport_get_song_pos_hint",
        "Read the song position hint string.",
        "transport",
        "get_song_pos_hint",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "position"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "transport_marker_jump",
        "Jump to the next or previous marker in the arrangement.",
        "transport",
        "marker_jump",
        TransportMarkerJumpRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("transport", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "transport_get_time_signature",
        "Read the current project time signature (e.g., 4/4, 3/4, 7/8). "
        "Returns numerator and denominator.",
        "transport",
        "get_time_signature",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "time-signature"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_set_time_signature",
        "Set the project time signature. numerator: beats per bar (1-16), "
        "denominator: beat value (1, 2, 4, 8, 16). Example: 4/4 for common "
        "time, 3/4 for waltz, 7/8 for odd meter.",
        "transport",
        "set_time_signature",
        TransportTimeSignatureRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("transport", "time-signature"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "transport_get_swing",
        "Read the current project swing/groove amount (0.0 = no swing, 1.0 = maximum swing).",
        "transport",
        "get_swing",
        EmptyFLToolRequest,
        "read",
        tags=("transport", "groove"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "transport_set_swing",
        "Set the project swing/groove amount. value range: 0.0 (no swing) to "
        "1.0 (maximum swing). Affects step-sequencer groove for all channels.",
        "transport",
        "set_swing",
        TransportSwingRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("transport", "groove"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "mixer_list_tracks",
        "List Mixer tracks and their state. The Mixer is FL Studio's FX/routing "
        "bus (not the Channel Rack). Each Mixer track is an FX chain with "
        "effects slots, volume, pan, and send routing. Channel Rack instruments "
        "route INTO mixer tracks via channels_route_to_mixer.",
        "mixer",
        "list_tracks",
        EmptyFLToolRequest,
        "read",
        tags=("mixer", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_get_track",
        "Inspect one Mixer track by index. Mixer tracks are FX/routing buses — "
        "they receive audio from Channel Rack channels via route_to_mixer. Mixer "
        "track 0 is the master output. Use channels_get_channel for instrument "
        "channel data.",
        "mixer",
        "get_track",
        MixerTrackRequest,
        "read",
        tags=("mixer", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_get_track_count",
        "Read the number of mixer tracks.",
        "mixer",
        "get_track_count",
        EmptyFLToolRequest,
        "read",
        tags=("mixer", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_get_meter_level",
        "Read the current meter level for one mixer track.",
        "mixer",
        "get_meter_level",
        MixerTrackRequest,
        "read",
        tags=("mixer", "meter"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_update_track",
        "Update Mixer track properties (volume, pan, mute, solo, arm, name). "
        "Affects the FX/routing bus level, NOT the source instrument level. To "
        "change instrument volume, use channels_update_channel instead.",
        "mixer",
        "update_track",
        MixerTrackUpdateRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "mixer_set_stereo_separation",
        "Set stereo separation for a mixer track.",
        "mixer",
        "set_stereo_separation",
        MixerStereoSeparationRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    # --- mixer domain: granular FL Studio API surface ---
    _spec(
        "mixer_get_track_color",
        "Read the color of a mixer track.",
        "mixer",
        "get_track_color",
        MixerTrackRequest,
        "read",
        tags=("mixer", "color"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_track_color",
        "Set the color of a mixer track.",
        "mixer",
        "set_track_color",
        MixerTrackColorRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "color"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_track_volume",
        "Read the volume of a mixer track.",
        "mixer",
        "get_track_volume",
        MixerTrackRequest,
        "read",
        tags=("mixer", "volume"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_track_volume",
        "Set volume (dB) for a Mixer track (the FX/routing bus row in the Mixer "
        "window). Mixer track 0 is the master. Does NOT affect Channel Rack "
        "instrument output level — use channels_set_volume for that.",
        "mixer",
        "set_track_volume",
        MixerTrackVolumeRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "volume"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_track_pan",
        "Read the pan position of a mixer track.",
        "mixer",
        "get_track_pan",
        MixerTrackRequest,
        "read",
        tags=("mixer", "pan"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_track_pan",
        "Set the pan position of a mixer track.",
        "mixer",
        "set_track_pan",
        MixerTrackPanRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "pan"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_mute_track",
        "Toggle or set the mute state of a mixer track.",
        "mixer",
        "mute_track",
        MixerMuteTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("mixer", "mute"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_solo_track",
        "Solo a mixer track.",
        "mixer",
        "solo_track",
        MixerSoloTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("mixer", "solo"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_arm_track",
        "Arm a mixer track for recording.",
        "mixer",
        "arm_track",
        MixerArmTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("mixer", "arm"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_is_track_armed",
        "Check whether a mixer track is armed for recording.",
        "mixer",
        "is_track_armed",
        MixerTrackRequest,
        "read",
        tags=("mixer", "arm"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_route_to",
        "Set or clear a routing connection between mixer tracks.",
        "mixer",
        "set_route_to",
        MixerRouteToRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "routing"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_route_send_level",
        "Read the send level for a mixer routing connection.",
        "mixer",
        "get_route_send_level",
        MixerRouteSendLevelRequest,
        "read",
        tags=("mixer", "routing"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_route_send_level",
        "Set the send level for a mixer routing connection.",
        "mixer",
        "set_route_send_level",
        MixerRouteSendLevelRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "routing"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_eq_gain",
        "Read the EQ gain for a band on a mixer track.",
        "mixer",
        "get_eq_gain",
        MixerEqGainRequest,
        "read",
        tags=("mixer", "eq"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_eq_gain",
        "Set the EQ gain for a band on a mixer track.",
        "mixer",
        "set_eq_gain",
        MixerEqGainRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "eq"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_eq_frequency",
        "Read the EQ frequency for a band on a mixer track.",
        "mixer",
        "get_eq_frequency",
        MixerEqFrequencyRequest,
        "read",
        tags=("mixer", "eq"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_set_eq_frequency",
        "Set the EQ frequency for a band on a mixer track.",
        "mixer",
        "set_eq_frequency",
        MixerEqFrequencyRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "eq"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "mixer_get_eq_bandwidth",
        "Read the EQ bandwidth for a band on a mixer track.",
        "mixer",
        "get_eq_bandwidth",
        MixerEqBandwidthRequest,
        "read",
        tags=("mixer", "eq"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "mixer_get_slot_count",
        "Read the number of effect slots on a Mixer track. Use this before "
        "iterating slots with mixer_get_slot_name or mixer_get_slot_plugin.",
        "mixer",
        "get_slot_count",
        MixerTrackRequest,
        "read",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_get_slot_name",
        "Read the effect plugin name loaded in a specific slot on a Mixer track. "
        "Returns empty string if the slot is empty.",
        "mixer",
        "get_slot_name",
        MixerSlotRequest,
        "read",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_is_slot_enabled",
        "Check whether an effect slot on a Mixer track is currently enabled (bypassed = False).",
        "mixer",
        "is_slot_enabled",
        MixerSlotRequest,
        "read",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_enable_slot",
        "Enable or bypass an effect slot on a Mixer track. Set enabled=False to bypass the effect.",
        "mixer",
        "enable_slot",
        MixerSlotEnableRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "mixer_get_slot_plugin",
        "Read the full plugin details (name, type, parameter count) loaded in a "
        "specific Mixer effect slot.",
        "mixer",
        "get_slot_plugin",
        MixerSlotRequest,
        "read",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "mixer_set_slot_plugin",
        "Load a plugin into a specific Mixer effect slot by name. The plugin "
        "must be installed. Use plugins_list_plugins to discover available "
        "plugin names.",
        "mixer",
        "set_slot_plugin",
        MixerSetSlotPluginRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("mixer", "fx"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_list",
        "List Channel Rack channels (instrument slots) and their current state. "
        "The Channel Rack holds instruments (samplers, synths, MIDI channels). "
        "Each channel can be routed to a Mixer track for FX processing via "
        "channels_route_to_mixer.",
        "channels",
        "list_channels",
        EmptyFLToolRequest,
        "read",
        tags=("channels", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "channels_get_channel",
        "Inspect one Channel Rack channel (instrument slot) by index. Returns "
        "instrument name, volume, pan, mute state, and routing. NOTE: This is a "
        "Channel Rack slot, not a Mixer track — use mixer_get_track for FX bus "
        "data.",
        "channels",
        "get_channel",
        ChannelRequest,
        "read",
        tags=("channels", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "channels_get_selected",
        "Read the currently selected channel rack channel.",
        "channels",
        "get_selected",
        EmptyFLToolRequest,
        "read",
        tags=("channels", "selection"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "channels_get_target_fx_track",
        "Read the mixer target for a channel rack channel.",
        "channels",
        "get_target_fx_track",
        ChannelRequest,
        "read",
        tags=("channels", "routing"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "channels_select_channel",
        "Select a channel rack channel.",
        "channels",
        "select_channel",
        ChannelSelectRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("channels", "selection"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "channels_update_channel",
        "Update Channel Rack channel properties (volume, pan, mute, solo, name, "
        "color). Affects the instrument's own output level before mixing. To "
        "control the Mixer FX bus, use mixer_update_track instead.",
        "channels",
        "update_channel",
        ChannelUpdateRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "channels_route_to_mixer",
        "Route a Channel Rack channel to a Mixer track. Required before applying "
        "Mixer FX to an instrument. Example workflow: "
        "channels_route_to_mixer(channel=0, track=1) → "
        "mixer_set_slot_plugin(track=1, slot=0, plugin='Fruity Reverb 2').",
        "channels",
        "route_to_mixer",
        ChannelRouteRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "routing"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "channels_get_step_sequence",
        "Read the step-sequencer state for a channel.",
        "channels",
        "get_step_sequence",
        ChannelRequest,
        "read",
        tags=("channels", "sequencer"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "channels_set_step_sequence",
        "Set the step-sequencer state for a channel.",
        "channels",
        "set_step_sequence",
        ChannelStepSequenceRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "sequencer"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "channels_trigger_note",
        "Trigger a note on the selected channel.",
        "channels",
        "trigger_note",
        ChannelTriggerNoteRequest,
        "direct",
        tags=("channels", "note"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_set_pitch",
        "Set channel pitch offset in cents.",
        "channels",
        "set_pitch",
        ChannelPitchRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "channels_duplicate",
        "Duplicate an existing channel where supported by the provider.",
        "channels",
        "duplicate",
        ChannelRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "edit"),
        annotations=_annotations(read_only=False),
    ),
    # --- channels domain: granular FL Studio API surface ---
    _spec(
        "channels_get_color",
        "Read the color of a channel rack channel.",
        "channels",
        "get_color",
        ChannelRequest,
        "read",
        tags=("channels", "color"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_set_color",
        "Set the color of a channel rack channel.",
        "channels",
        "set_color",
        ChannelColorRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "color"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_get_volume",
        "Read the volume of a channel rack channel.",
        "channels",
        "get_volume",
        ChannelRequest,
        "read",
        tags=("channels", "volume"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_set_volume",
        "Set the output volume for a Channel Rack channel (instrument slot). "
        "Affects instrument output before it reaches the Mixer. For Mixer-level "
        "volume control use mixer_set_volume or mixer_set_track_volume.",
        "channels",
        "set_volume",
        ChannelVolumeRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "volume"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_get_pan",
        "Read the pan position of a channel rack channel.",
        "channels",
        "get_pan",
        ChannelRequest,
        "read",
        tags=("channels", "pan"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_set_pan",
        "Set the pan position of a channel rack channel.",
        "channels",
        "set_pan",
        ChannelPanRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "pan"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_mute",
        "Toggle or set the mute state of a channel rack channel.",
        "channels",
        "mute",
        ChannelMuteRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("channels", "mute"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_solo",
        "Solo a channel rack channel.",
        "channels",
        "solo",
        ChannelSoloRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("channels", "solo"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_get_type",
        "Read the instrument type of a channel rack channel.",
        "channels",
        "get_type",
        ChannelRequest,
        "read",
        tags=("channels", "type"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_get_midi_in_port",
        "Read the MIDI input port assigned to a channel rack channel.",
        "channels",
        "get_midi_in_port",
        ChannelRequest,
        "read",
        tags=("channels", "midi"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_get_grid_bit",
        "Read the state of a step-sequencer grid bit for a channel.",
        "channels",
        "get_grid_bit",
        ChannelGridBitRequest,
        "read",
        tags=("channels", "sequencer"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "channels_set_grid_bit",
        "Set the state of a step-sequencer grid bit for a channel.",
        "channels",
        "set_grid_bit",
        ChannelGridBitRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "sequencer"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_quick_quantize",
        "Quick-quantize note positions for a channel.",
        "channels",
        "quick_quantize",
        ChannelQuickQuantizeRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("channels", "quantize"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "channels_load_sample",
        "Load an audio sample file into a Channel Rack channel. file_path must "
        "be an absolute path to a supported audio file (WAV, MP3, OGG, FLAC). "
        "Essential for building beats and arrangements from audio files.",
        "channels",
        "load_sample",
        ChannelLoadSampleRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("channels", "sample"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "patterns_list",
        "List available patterns.",
        "patterns",
        "list_patterns",
        EmptyFLToolRequest,
        "read",
        tags=("patterns", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "patterns_select",
        "Select an existing pattern.",
        "patterns",
        "select_pattern",
        PatternRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("patterns", "selection"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "patterns_create",
        "Create a new empty pattern (MIDI container). Workflow: patterns_create "
        "→ select it → piano_roll_send_notes to add notes → playlist_place_clip "
        "to place in the arrangement. Patterns hold the MIDI data; playlist "
        "clips reference them.",
        "patterns",
        "create_pattern",
        PatternCreateRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("patterns", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "patterns_rename",
        "Rename an existing pattern.",
        "patterns",
        "rename_pattern",
        PatternRenameRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("patterns", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "patterns_set_length",
        "Set the length of a pattern in beats.",
        "patterns",
        "set_length",
        PatternLengthRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("patterns", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    # --- patterns domain: granular FL Studio API surface ---
    _spec(
        "patterns_get_color",
        "Read the color of a pattern.",
        "patterns",
        "get_color",
        PatternRequest,
        "read",
        tags=("patterns", "color"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "patterns_set_color",
        "Set the color of a pattern.",
        "patterns",
        "set_color",
        PatternColorRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("patterns", "color"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "patterns_clone",
        "Clone an existing pattern.",
        "patterns",
        "clone",
        PatternCloneRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("patterns", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "patterns_jump_to",
        "Jump to a specific pattern by index.",
        "patterns",
        "jump_to",
        PatternJumpToRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("patterns", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "patterns_is_default",
        "Check whether a pattern is still in its default (empty) state.",
        "patterns",
        "is_default",
        PatternRequest,
        "read",
        tags=("patterns", "query"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "playlist_list_tracks",
        "List playlist tracks and their current state.",
        "playlist",
        "list_tracks",
        EmptyFLToolRequest,
        "read",
        tags=("playlist", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "playlist_get_track",
        "Inspect one playlist track.",
        "playlist",
        "get_track",
        PlaylistTrackRequest,
        "read",
        tags=("playlist", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "playlist_update_track",
        "Rename a playlist track.",
        "playlist",
        "update_track",
        PlaylistTrackUpdateRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "playlist_get_arrangement",
        "Read arrangement-level state for one playlist arrangement.",
        "playlist",
        "get_arrangement",
        PlaylistArrangementRequest,
        "read",
        tags=("playlist", "arrangement"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "playlist_list_clips",
        "List clips for one playlist arrangement or track.",
        "playlist",
        "list_clips",
        PlaylistClipRequest,
        "read",
        tags=("playlist", "clip"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "playlist_place_clip",
        "Place a pattern as a clip on the Playlist arrangement. position is in "
        "beats from the start. pattern_index references a pattern created with "
        "patterns_create. This is the final step in the patterns → piano roll "
        "→ playlist workflow.",
        "playlist",
        "place_clip",
        PlaylistPlaceClipRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "clip"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_move_clip",
        "Move an existing playlist clip.",
        "playlist",
        "move_clip",
        PlaylistMoveClipRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "clip"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "playlist_delete_clip",
        "Delete a playlist clip.",
        "playlist",
        "delete_clip",
        PlaylistClipRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "clip"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    _spec(
        "playlist_list_markers",
        "List arrangement markers in the playlist.",
        "playlist",
        "list_markers",
        PlaylistMarkerRequest,
        "read",
        tags=("playlist", "marker"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "playlist_create_marker",
        "Create a marker in the playlist arrangement.",
        "playlist",
        "create_marker",
        PlaylistCreateMarkerRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "marker"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_update_marker",
        "Update a marker in the playlist arrangement.",
        "playlist",
        "update_marker",
        PlaylistUpdateMarkerRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "marker"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "playlist_delete_marker",
        "Delete a marker from the playlist arrangement.",
        "playlist",
        "delete_marker",
        PlaylistMarkerRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "marker"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    # --- playlist domain: granular FL Studio API surface ---
    _spec(
        "playlist_get_track_color",
        "Read the color of a playlist track.",
        "playlist",
        "get_track_color",
        PlaylistTrackRequest,
        "read",
        tags=("playlist", "color"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "playlist_set_track_color",
        "Set the color of a playlist track.",
        "playlist",
        "set_track_color",
        PlaylistTrackColorRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("playlist", "color"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_mute_track",
        "Toggle or set the mute state of a playlist track.",
        "playlist",
        "mute_track",
        PlaylistMuteTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("playlist", "mute"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_solo_track",
        "Solo a playlist track.",
        "playlist",
        "solo_track",
        PlaylistSoloTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("playlist", "solo"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_select_track",
        "Select a playlist track.",
        "playlist",
        "select_track",
        PlaylistSelectTrackRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("playlist", "selection"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "playlist_get_track_activity",
        "Read the current activity level of a playlist track.",
        "playlist",
        "get_track_activity",
        PlaylistTrackRequest,
        "read",
        tags=("playlist", "meter"),
        annotations=_annotations(read_only=True),
    ),
    _spec(
        "piano_roll_get_state",
        "Read piano-roll note state.",
        "piano-roll",
        "get_state",
        EmptyFLToolRequest,
        "read",
        tags=("piano-roll", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "piano_roll_send_notes",
        "Write MIDI notes into the Piano Roll of the currently selected pattern. "
        "Each note: {note: int (MIDI 0-127), time: float (beats), duration: "
        "float (beats), velocity: int (1-127)}. Select a pattern first with "
        "patterns_select.",
        "piano-roll",
        "send_notes",
        PianoRollNotesRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "piano_roll_delete_notes",
        "Delete selected piano-roll notes.",
        "piano-roll",
        "delete_notes",
        PianoRollDeleteNotesRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "piano_roll_clear",
        "Clear all notes from the active piano roll.",
        "piano-roll",
        "clear",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "edit"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    _spec(
        "piano_roll_quantize",
        "Quantize active piano-roll notes to a rhythmic grid.",
        "piano-roll",
        "quantize",
        PianoRollQuantizeRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "transform"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "piano_roll_transpose",
        "Transpose active piano-roll notes by a number of semitones.",
        "piano-roll",
        "transpose",
        PianoRollTransposeRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "transform"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "piano_roll_humanize",
        "Humanize timing and velocity for active piano-roll notes.",
        "piano-roll",
        "humanize",
        PianoRollHumanizeRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "transform"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "piano_roll_generate_chords",
        "Generate chord notes in the active piano roll.",
        "piano-roll",
        "generate_chords",
        PianoRollGenerateChordRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "composition"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "piano_roll_generate_melody",
        "Generate a melody in the active piano roll.",
        "piano-roll",
        "generate_melody",
        PianoRollGenerateMelodyRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "composition"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "piano_roll_generate_bass",
        "Generate a bass line in the active piano roll.",
        "piano-roll",
        "generate_bass",
        PianoRollGenerateBassRequest,
        "transaction",
        rollback_class="fully_transactional",
        tags=("piano-roll", "composition"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "plugins_list",
        "List plugins or plugin slots for a channel.",
        "plugins",
        "list_plugins",
        PluginSlotRequest,
        "read",
        tags=("plugins", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_parameters",
        "List plugin parameters for a channel/plugin slot.",
        "plugins",
        "get_parameters",
        PluginSlotRequest,
        "read",
        tags=("plugins", "parameters"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_parameter",
        "Read one plugin parameter value.",
        "plugins",
        "get_parameter",
        PluginParameterRequest,
        "read",
        tags=("plugins", "parameters"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_set_parameter",
        "Set one plugin parameter value.",
        "plugins",
        "set_parameter",
        PluginSetParameterRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "parameters"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "plugins_next_preset",
        "Cycle to the next preset for a plugin on a channel. Blind navigation — "
        "use plugins_get_preset_name to discover preset names first, then "
        "plugins_load_preset_by_name for precise selection.",
        "plugins",
        "next_preset",
        PluginSlotRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "preset"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "plugins_is_valid",
        "Check whether a plugin slot or target plugin is valid.",
        "plugins",
        "is_valid",
        PluginSlotRequest,
        "read",
        tags=("plugins", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_name",
        "Read the resolved plugin name for a slot.",
        "plugins",
        "get_name",
        PluginSlotRequest,
        "read",
        tags=("plugins", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_parameter_count",
        "Read the number of parameters exposed by a plugin slot.",
        "plugins",
        "get_parameter_count",
        PluginSlotRequest,
        "read",
        tags=("plugins", "parameters"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_parameter_name",
        "Read the FL wrapper parameter name for a plugin parameter index.",
        "plugins",
        "get_parameter_name",
        PluginParameterIndexRequest,
        "read",
        tags=("plugins", "parameters", "raw", "enumeration"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_preset_count",
        "Read the number of presets exposed by a plugin slot.",
        "plugins",
        "get_preset_count",
        PluginSlotRequest,
        "read",
        tags=("plugins", "preset"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_show_window",
        "Show or hide a plugin window.",
        "plugins",
        "show_window",
        PluginWindowRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "window"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "plugins_load",
        "Load a plugin into a slot.",
        "plugins",
        "load",
        PluginLoadRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("plugins", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "plugins_replace",
        "Replace the plugin currently loaded in a slot.",
        "plugins",
        "replace",
        PluginReplaceRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("plugins", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "plugins_prev_preset",
        "Cycle to the previous preset for a plugin on a channel. Blind navigation "
        "— use plugins_get_preset_name to discover preset names first, then "
        "plugins_load_preset_by_name for precise selection.",
        "plugins",
        "prev_preset",
        PluginSlotRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "preset"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "plugins_get_preset_name",
        "Read the name of a plugin preset by index. Use to build a preset menu "
        "before calling plugins_load_preset_by_name.",
        "plugins",
        "get_preset_name",
        PluginSlotRequest,
        "read",
        tags=("plugins", "preset"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_load_preset_by_name",
        "Load a plugin preset by exact name. More reliable than next/prev_preset "
        "for agentic workflows. Use plugins_get_preset_name to discover "
        "available preset names before calling this.",
        "plugins",
        "load_preset_by_name",
        PluginPresetNameRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("plugins", "preset"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    # --- plugins domain: granular FL Studio API surface ---
    _spec(
        "plugins_get_param_value_string",
        "Read the string representation of a plugin parameter value.",
        "plugins",
        "get_param_value_string",
        PluginParamValueStringRequest,
        "read",
        tags=("plugins", "parameters"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_color",
        "Read the color of a plugin instance.",
        "plugins",
        "get_color",
        PluginColorRequest,
        "read",
        tags=("plugins", "color"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_pad_info",
        "Read performance-pad information for a plugin.",
        "plugins",
        "get_pad_info",
        PluginPadInfoRequest,
        "read",
        tags=("plugins", "pad"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    # --- plugins domain: declarative plugin-profile support ---
    _spec(
        "plugins_inventory_scan",
        "Scan installed AU/VST/VST3/CLAP bundles, FL plugin database entries, "
        "and local preset assets for profile-aware plugin workflows.",
        "plugins",
        "inventory_scan",
        PluginInventoryScanRequest,
        "read",
        tags=("plugins", "profile", "inventory", "browser", "preset"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_list_profiles",
        "List built-in and local plugin profiles for Sylenth1, Serum, FabFilter, "
        "ShaperBox, CamelCrusher, Drumazon, ValhallaRoom, Trash, and other targets.",
        "plugins",
        "list_profiles",
        PluginProfileListRequest,
        "read",
        tags=("plugins", "profile", "sylenth", "serum", "fabfilter", "trash"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_get_profile",
        "Read a plugin profile with inventory, calibration status, semantic controls, "
        "and readback guidance.",
        "plugins",
        "get_profile",
        PluginProfileRequest,
        "read",
        tags=("plugins", "profile", "schema", "calibration"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_resolve_profile",
        "Resolve a natural plugin query such as Sylenth cutoff, FabFilter Pro-Q, "
        "Serum macro, or iZotope Trash to profile and inventory candidates.",
        "plugins",
        "resolve_profile",
        PluginProfileResolveRequest,
        "read",
        tags=("plugins", "profile", "search", "browser", "sylenth", "fabfilter"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_probe_instance",
        "Probe a live FL plugin slot for validity, reported name, and parameter count.",
        "plugins",
        "probe_instance",
        PluginProfileInstanceRequest,
        "read",
        tags=("plugins", "profile", "calibration", "live-probe"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_enumerate_parameters",
        "Enumerate FL-exposed raw plugin parameters by index, name, value, and "
        "value string when the host exposes them.",
        "plugins",
        "enumerate_parameters",
        PluginEnumerateParametersRequest,
        "read",
        tags=("plugins", "profile", "parameters", "raw", "enumeration"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_probe_loadability",
        "Probe a priority plugin target for local inventory, live validity, and "
        "raw parameter readability.",
        "plugins",
        "probe_loadability",
        PluginProfileInstanceRequest,
        "read",
        tags=("plugins", "profile", "priority", "live-probe"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_generate_raw_profile",
        "Generate a deterministic raw profile preview from FL parameter enumeration.",
        "plugins",
        "generate_raw_profile",
        PluginGenerateRawProfileRequest,
        "read",
        tags=("plugins", "profile", "raw", "support-matrix"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_learn_parameter",
        "Create a transient semantic-control-to-FL-parameter mapping from a live "
        "calibration observation.",
        "plugins",
        "learn_parameter",
        PluginProfileLearnRequest,
        "read",
        tags=("plugins", "profile", "calibration", "parameters"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_validate_profile",
        "Validate profile, local inventory, and calibration readiness for mapped execution.",
        "plugins",
        "validate_profile",
        PluginProfileValidateRequest,
        "read",
        tags=("plugins", "profile", "validation", "calibration"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_verify_profile_controls",
        "Verify calibrated semantic plugin controls with live readback.",
        "plugins",
        "verify_profile_controls",
        PluginProfileVerifyRequest,
        "read",
        tags=("plugins", "profile", "calibration", "readback"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_write_calibration_overlay",
        "Write a machine-local semantic-control calibration overlay after live "
        "parameter index verification.",
        "plugins",
        "write_calibration_overlay",
        PluginCalibrationWriteRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "profile", "calibration", "local-overlay"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "plugins_get_mapped_parameter",
        "Read a semantic plugin control through a calibrated FL wrapper parameter index.",
        "plugins",
        "get_mapped_parameter",
        PluginMappedParameterRequest,
        "read",
        tags=("plugins", "profile", "parameters", "readback"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_set_mapped_parameter",
        "Set a semantic plugin control such as Sylenth cutoff through a calibrated "
        "FL wrapper parameter index with readback when available.",
        "plugins",
        "set_mapped_parameter",
        PluginSetMappedParameterRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("plugins", "profile", "parameters", "sylenth", "cutoff", "fabfilter", "serum"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "plugins_load_profile_preset",
        "Load a profile-scoped plugin preset, bank, or wrapper-state asset when the "
        "plugin and preset path are verified.",
        "plugins",
        "load_profile_preset",
        PluginProfilePresetRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("plugins", "profile", "preset", "browser"),
        annotations=_annotations(read_only=False, idempotent=False),
    ),
    _spec(
        "plugins_list_local_presets",
        "List local plugin preset, bank, and FL wrapper-state assets with profile hints.",
        "plugins",
        "list_local_presets",
        PluginLocalPresetsRequest,
        "read",
        tags=("plugins", "profile", "preset", "inventory", "sylenth"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_reconcile_inventory",
        "Reconcile system plugin bundles, FL plugin database entries, presets, and "
        "profile seeds into machine-readable support states.",
        "plugins",
        "reconcile_inventory",
        PluginReconcileInventoryRequest,
        "read",
        tags=("plugins", "profile", "inventory", "validation"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_priority_support_audit",
        "Audit paid, pro-suite, and popular/useful plugin support priorities.",
        "plugins",
        "priority_support_audit",
        PluginPrioritySupportAuditRequest,
        "read",
        tags=("plugins", "profile", "priority", "support-matrix", "audit"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "plugins_export_support_matrix",
        "Export the priority-aware plugin support matrix for agents and docs.",
        "plugins",
        "export_support_matrix",
        PluginPrioritySupportAuditRequest,
        "read",
        tags=("plugins", "profile", "priority", "support-matrix"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_show_window",
        "Show or hide a named FL Studio window.",
        "ui",
        "show_window",
        UIShowWindowRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "window"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "ui_get_visibility",
        "Inspect visibility for a named FL Studio window.",
        "ui",
        "get_visibility",
        UIWindowRequest,
        "read",
        tags=("ui", "window"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    # --- ui domain: granular FL Studio API surface ---
    _spec(
        "ui_hide_window",
        "Hide a named FL Studio window.",
        "ui",
        "hide_window",
        UIWindowRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "window"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "ui_get_focused",
        "Read the index of the currently focused FL Studio window.",
        "ui",
        "get_focused",
        UIWindowIndexRequest,
        "read",
        tags=("ui", "focus"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_set_focused",
        "Set focus to a specific FL Studio window by index.",
        "ui",
        "set_focused",
        UIWindowIndexRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "focus"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "ui_get_focused_form_caption",
        "Read the caption of the currently focused FL Studio form.",
        "ui",
        "get_focused_form_caption",
        EmptyFLToolRequest,
        "read",
        tags=("ui", "focus"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_get_focused_plugin_name",
        "Read the plugin name of the currently focused FL Studio plugin window.",
        "ui",
        "get_focused_plugin_name",
        EmptyFLToolRequest,
        "read",
        tags=("ui", "focus"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_scroll_window",
        "Scroll a FL Studio window by a given offset.",
        "ui",
        "scroll_window",
        UIScrollWindowRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "ui_next_window",
        "Switch focus to the next FL Studio window.",
        "ui",
        "next_window",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "ui_get_snap_mode",
        "Read the current snap mode for the FL Studio UI.",
        "ui",
        "get_snap_mode",
        EmptyFLToolRequest,
        "read",
        tags=("ui", "snap"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_set_snap_mode",
        "Set the snap mode for the FL Studio UI.",
        "ui",
        "set_snap_mode",
        UISnapModeRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("ui", "snap"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "ui_get_hint_msg",
        "Read the current hint message displayed in FL Studio.",
        "ui",
        "get_hint_msg",
        EmptyFLToolRequest,
        "read",
        tags=("ui", "hint"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "ui_set_hint_msg",
        "Set the hint message displayed in the FL Studio toolbar.",
        "ui",
        "set_hint_msg",
        UIHintMsgRequest,
        "direct",
        tags=("ui", "hint"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "ui_get_step_edit_mode",
        "Read the current step-edit mode state in FL Studio.",
        "ui",
        "get_step_edit_mode",
        EmptyFLToolRequest,
        "read",
        tags=("ui", "edit"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_version",
        "Read the current FL Studio version.",
        "general",
        "get_version",
        EmptyFLToolRequest,
        "read",
        tags=("general", "project"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_project_title",
        "Read the current FL Studio project title.",
        "general",
        "get_project_title",
        EmptyFLToolRequest,
        "read",
        tags=("general", "project"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_project_path",
        "Read the current FL Studio project path.",
        "general",
        "get_project_path",
        EmptyFLToolRequest,
        "read",
        tags=("general", "project"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_project_state",
        "Read mutable state such as dirty and read-only project flags.",
        "general",
        "get_project_state",
        EmptyFLToolRequest,
        "read",
        tags=("general", "project"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_save_project",
        "Save the current FL Studio project.",
        "general",
        "save_project",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("general", "project"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "general_open_project",
        "Open an FL Studio project by path.",
        "general",
        "open_project",
        ProjectPathRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("general", "project"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "general_save_project_as",
        "Save the current FL Studio project to a new path.",
        "general",
        "save_project_as",
        ProjectPathRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("general", "project"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "general_undo",
        "Undo the latest FL Studio action.",
        "general",
        "undo",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("general", "project"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "general_redo",
        "Redo the latest FL Studio action.",
        "general",
        "redo",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("general", "project"),
        annotations=_annotations(read_only=False),
    ),
    # --- general domain: granular FL Studio API surface ---
    _spec(
        "general_get_changed_flag",
        "Read whether the current FL Studio project has unsaved changes.",
        "general",
        "get_changed_flag",
        EmptyFLToolRequest,
        "read",
        tags=("general", "project"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_rec_ppq",
        "Read the recording pulses-per-quarter-note resolution.",
        "general",
        "get_rec_ppq",
        EmptyFLToolRequest,
        "read",
        tags=("general", "timing"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_metronome",
        "Read the current metronome enabled state.",
        "general",
        "get_metronome",
        EmptyFLToolRequest,
        "read",
        tags=("general", "metronome"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_precount",
        "Read the recording pre-count enabled state.",
        "general",
        "get_precount",
        EmptyFLToolRequest,
        "read",
        tags=("general", "recording"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_save_undo",
        "Save an undo checkpoint with a descriptive name.",
        "general",
        "save_undo",
        GeneralSaveUndoRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("general", "undo"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "general_restore_undo",
        "Restore the most recent undo checkpoint.",
        "general",
        "restore_undo",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("general", "undo"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "general_get_undo_history_pos",
        "Read the current position in the undo history stack.",
        "general",
        "get_undo_history_pos",
        EmptyFLToolRequest,
        "read",
        tags=("general", "undo"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_get_undo_history_count",
        "Read the total number of entries in the undo history stack.",
        "general",
        "get_undo_history_count",
        EmptyFLToolRequest,
        "read",
        tags=("general", "undo"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "general_new_project",
        "Create a new FL Studio project. WARNING: If save_current=False "
        "(default), ALL unsaved changes to the current project are permanently "
        "lost. Always call general_save_project first to preserve work.",
        "general",
        "new_project",
        GeneralNewProjectRequest,
        "transaction",
        rollback_class="unsafe_raw",
        tags=("general", "project"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    _spec(
        "general_close_project",
        "Close the current FL Studio project. WARNING: Any unsaved changes are "
        "permanently lost. Always call general_save_project first to preserve "
        "work.",
        "general",
        "close_project",
        EmptyFLToolRequest,
        "transaction",
        rollback_class="unsafe_raw",
        tags=("general", "project"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    _spec(
        "render_export",
        "Start an FL Studio export/render task.",
        "render",
        "export",
        RenderExportRequest,
        "direct",
        tags=("render", "task"),
        annotations=_annotations(read_only=False),
        timeout=30.0,
        task=True,
    ),
    _spec(
        "render_get_job",
        "Read the status of a render job.",
        "render",
        "get_job",
        RenderJobRequest,
        "read",
        response_model=FLTaskToolResponse,
        tags=("render", "task"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "render_cancel_job",
        "Cancel an in-flight render job.",
        "render",
        "cancel_job",
        RenderJobRequest,
        "transaction",
        response_model=FLTaskToolResponse,
        rollback_class="best_effort",
        tags=("render", "task"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "audio_analyze",
        "Start an analysis task for rendered or source audio.",
        "audio",
        "analyze",
        AudioAnalyzeRequest,
        "direct",
        tags=("audio", "task"),
        annotations=_annotations(read_only=False),
        timeout=30.0,
        task=True,
    ),
    _spec(
        "audio_get_analysis",
        "Read the status of an audio analysis task.",
        "audio",
        "get_analysis",
        AudioAnalysisRequest,
        "read",
        response_model=FLTaskToolResponse,
        tags=("audio", "task"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "audio_cancel_analysis",
        "Cancel an in-flight audio analysis task.",
        "audio",
        "cancel_analysis",
        AudioAnalysisRequest,
        "transaction",
        response_model=FLTaskToolResponse,
        rollback_class="best_effort",
        tags=("audio", "task"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    # --- device domain: FL Studio device/controller surface ---
    _spec(
        "device_is_assigned",
        "Check whether the current MIDI device is assigned to FL Studio.",
        "device",
        "is_assigned",
        EmptyFLToolRequest,
        "read",
        tags=("device", "status"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "device_get_name",
        "Read the name of the assigned MIDI device.",
        "device",
        "get_name",
        EmptyFLToolRequest,
        "read",
        tags=("device", "info"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "device_get_port_number",
        "Read the port number of the assigned MIDI device.",
        "device",
        "get_port_number",
        EmptyFLToolRequest,
        "read",
        tags=("device", "info"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "device_midi_out_msg",
        "Send a raw MIDI output message through the device module.",
        "device",
        "midi_out_msg",
        DeviceMidiOutMsgRequest,
        "direct",
        tags=("device", "midi"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "device_midi_out_sysex",
        "Send a SysEx message through the device module.",
        "device",
        "midi_out_sysex",
        DeviceMidiOutSysexRequest,
        "direct",
        tags=("device", "midi"),
        annotations=_annotations(read_only=False),
    ),
    # --- arrangement domain: FL Studio arrangement surface ---
    _spec(
        "arrangement_get_current_time",
        "Read the current time position in the arrangement.",
        "arrangement",
        "get_current_time",
        ArrangementTimeRequest,
        "read",
        tags=("arrangement", "time"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "arrangement_get_time_hint",
        "Read a formatted time hint for the arrangement.",
        "arrangement",
        "get_time_hint",
        ArrangementTimeHintRequest,
        "read",
        tags=("arrangement", "time"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "arrangement_get_selection_start",
        "Read the start position of the current arrangement selection.",
        "arrangement",
        "get_selection_start",
        EmptyFLToolRequest,
        "read",
        tags=("arrangement", "selection"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "arrangement_get_selection_end",
        "Read the end position of the current arrangement selection.",
        "arrangement",
        "get_selection_end",
        EmptyFLToolRequest,
        "read",
        tags=("arrangement", "selection"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "arrangement_jump_to_marker",
        "Jump to the next or previous arrangement marker.",
        "arrangement",
        "jump_to_marker",
        ArrangementJumpToMarkerRequest,
        "transaction",
        rollback_class="best_effort",
        tags=("arrangement", "navigation"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "automation_list_clips",
        "List all automation clips in the current FL Studio project. Automation "
        "clips control parameter values over time (volume curves, filter sweeps, "
        "effect parameters). Use this to discover what automation is already "
        "present.",
        "automation",
        "list_clips",
        EmptyFLToolRequest,
        "read",
        tags=("automation", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "automation_get_clip",
        "Inspect one automation clip by index, returning its name, linked "
        "parameter, and point count.",
        "automation",
        "get_clip",
        AutomationClipRequest,
        "read",
        tags=("automation", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "automation_create_clip",
        "Create a new automation clip. Workflow: automation_create_clip → "
        "automation_write_points to add the time-value curve → "
        "automation_link_to_parameter to connect to a Mixer/Channel/Plugin "
        "parameter.",
        "automation",
        "create_clip",
        AutomationCreateRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("automation", "edit"),
        annotations=_annotations(read_only=False),
    ),
    _spec(
        "automation_delete_clip",
        "Delete an automation clip by index. This is irreversible without undo. "
        "Use `general_undo` to recover if needed.",
        "automation",
        "delete_clip",
        AutomationClipRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("automation", "edit"),
        annotations=_annotations(read_only=False, destructive=True),
    ),
    _spec(
        "automation_write_points",
        'Write automation curve points to a clip. Each point: {"time": float '
        '(beats), "value": float (0.0-1.0 normalized)}. Replaces ALL existing '
        "points. Followed by automation_link_to_parameter to attach to a "
        "parameter.",
        "automation",
        "write_points",
        AutomationWritePointsRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("automation", "edit"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
    _spec(
        "automation_read_points",
        "Read all automation curve points from a clip. Returns a list of "
        '{"time": float (beats), "value": float (0.0\u20131.0)} dicts.',
        "automation",
        "read_points",
        AutomationClipRequest,
        "read",
        tags=("automation", "state"),
        annotations=_annotations(read_only=True, idempotent=True),
    ),
    _spec(
        "automation_link_to_parameter",
        "Link an automation clip to a target parameter. target_type: 'mixer' "
        "(Mixer track param), 'channel' (Channel Rack param), 'plugin' (plugin "
        "parameter). target_index: track/channel index. parameter_index: param "
        "slot index.",
        "automation",
        "link_to_parameter",
        AutomationLinkRequest,
        "transaction",
        rollback_class="checkpointed",
        tags=("automation", "link"),
        annotations=_annotations(read_only=False, idempotent=True),
    ),
)

FL_TOOL_BY_NAME: dict[str, FLToolSpec] = {spec.name: spec for spec in FL_TOOL_SPECS}
FL_TOOL_BY_CHANGE: dict[tuple[str, str], FLToolSpec] = {
    (spec.domain, spec.operation): spec for spec in FL_TOOL_SPECS
}


def _tool_names_for_domains(domains: list[str]) -> list[str]:
    domain_set = set(domains)
    return sorted(spec.name for spec in FL_TOOL_SPECS if spec.domain in domain_set)


PROVIDER_MATRIX["piano-roll-script"]["capabilities"] = _tool_names_for_domains(
    ["piano-roll", "patterns"]
)
PROVIDER_MATRIX["midi-fallback"]["capabilities"] = _tool_names_for_domains(
    ["connection", "midi", "channels", "transport", "device"]
)
PROVIDER_MATRIX["flapi-live"]["supported_domains"] = sorted({spec.domain for spec in FL_TOOL_SPECS})
PROVIDER_MATRIX["flapi-live"]["capabilities"] = sorted(spec.name for spec in FL_TOOL_SPECS)


def _payload_from_request(request: FLToolRequest) -> dict[str, object]:
    return request.model_dump(
        exclude_none=True,
        exclude={"provider", "session_label"},
    )


def _provider_hint(spec: FLToolSpec, request: FLToolRequest) -> str:
    if request.provider == "auto":
        return default_provider_for_operation(spec.domain, spec.operation)
    return request.provider


def _bridge_provider_hint(request: FLToolRequest) -> str | None:
    return None if request.provider == "auto" else request.provider


def _task_request_id(request: FLToolRequest) -> str | None:
    for field_name in ("job_id", "analysis_id"):
        value = getattr(request, field_name, None)
        if isinstance(value, str):
            return value
    return None


def _task_record_artifact_uri(record: ProviderTaskRecord | None) -> str | None:
    if record is None:
        return None
    artifact_uri = record.result.get("artifact_uri")
    if isinstance(artifact_uri, str):
        return artifact_uri
    if record.artifacts:
        return record.artifacts[0]
    return None


def _task_response(
    spec: FLToolSpec,
    *,
    request: FLToolRequest,
    record: ProviderTaskRecord | None,
) -> dict[str, object]:
    task_id = _task_request_id(request) or f"{spec.name}-{uuid4().hex[:12]}"
    response_payload: dict[str, object]
    if record is None:
        error_code = "unknown_job" if spec.domain == "render" else "unknown_analysis"
        response_payload = {
            "status": "error",
            "tool": spec.name,
            "domain": spec.domain,
            "operation": spec.operation,
            "provider": _provider_hint(spec, request),
            "bridge_mode": "runtime-state",
            "execution_id": task_id,
            "message": error_code,
            "task": {
                "id": task_id,
                "state": "failed",
                "progress": 0.0,
                "kind": spec.domain,
                "artifact_uri": None,
                "error": error_code,
                "result": {},
            },
            "error_code": error_code,
        }
        return spec.response_model.model_validate(response_payload).model_dump()

    response_payload = {
        "status": "ok",
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "provider": record.provider,
        "bridge_mode": "runtime-state",
        "execution_id": record.id,
        "message": record.message or f"{spec.name} completed.",
        "task": {
            "id": record.id,
            "state": record.state,
            "progress": _result_progress(record.result.get("progress", 0.0)),
            "kind": record.kind,
            "artifact_uri": _task_record_artifact_uri(record),
            "error": None,
            "result": dict(record.result),
        },
        "error_code": None,
    }
    return spec.response_model.model_validate(response_payload).model_dump()


def _runtime_task_result(spec: FLToolSpec, request: FLToolRequest) -> dict[str, object]:
    runtime_state = get_runtime_state()
    task_id = _task_request_id(request)
    if task_id is None:
        return _task_response(spec, request=request, record=None)

    if spec.domain == "render" and spec.operation == "get_job":
        record = runtime_state.get_render_job(task_id)
    elif spec.domain == "render" and spec.operation == "cancel_job":
        record = runtime_state.cancel_render_job(task_id)
    elif spec.domain == "audio" and spec.operation == "get_analysis":
        record = runtime_state.get_audio_analysis(task_id)
    elif spec.domain == "audio" and spec.operation == "cancel_analysis":
        record = runtime_state.cancel_audio_analysis(task_id)
    else:  # pragma: no cover - defensive branch for future task specs
        record = None
    return _task_response(spec, request=request, record=record)


def _persist_runtime_task(
    spec: FLToolSpec,
    request: FLToolRequest,
    *,
    provider: str,
    bridge_mode: str,
    execution_id: str | None,
    message: str,
    result: dict[str, object],
) -> ProviderTaskRecord | None:
    runtime_state = get_runtime_state()
    task_result = {
        **dict(result),
        "execution_id": execution_id,
        "bridge_mode": bridge_mode,
        "provider": provider,
        "message": message,
    }
    native_task_id = _native_task_id()
    if native_task_id is not None:
        if execution_id is not None:
            task_result["bridge_execution_id"] = execution_id
        task_result["task_id"] = native_task_id
        task_result["execution_id"] = native_task_id
        if spec.domain == "render":
            task_result["job_id"] = native_task_id
        elif spec.domain == "audio":
            task_result["analysis_id"] = native_task_id
    payload = _payload_from_request(request)

    if spec.domain == "render" and spec.operation == "export":
        return runtime_state.create_render_job(
            provider=provider,
            tool=spec.name,
            operation=f"{spec.domain}.{spec.operation}",
            payload=payload,
            result=task_result,
        )
    if spec.domain == "audio" and spec.operation == "analyze":
        return runtime_state.create_audio_analysis(
            provider=provider,
            tool=spec.name,
            operation=f"{spec.domain}.{spec.operation}",
            payload=payload,
            result=task_result,
        )
    return None


def _build_response_payload(spec: FLToolSpec, result: BridgeExecutionResult) -> dict[str, object]:
    """Build the standard response dict from a bridge execution result."""
    payload: dict[str, object] = {
        "status": "ok" if result.success else "error",
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "provider": result.provider,
        "bridge_mode": result.bridge_mode,
        "execution_id": result.execution_id,
        "message": result.message,
        "result": result.result,
        "error_code": result.error_code,
    }
    if result.bridge_mode == "mock":
        payload["mock_mode_warning"] = (
            "This operation was simulated — no real FL Studio state was modified."
        )
    return payload


def _bridge_read_result(spec: FLToolSpec, request: FLToolRequest) -> dict[str, object]:
    if spec.response_model is FLTaskToolResponse:
        return _runtime_task_result(spec, request)

    bridge = DEFAULT_BRIDGE
    payload = _payload_from_request(request)
    result = bridge.execute_operation(
        domain=spec.domain,
        operation=spec.operation,
        payload=payload,
        provider=_bridge_provider_hint(request),
    )
    response_payload = _build_response_payload(spec, result)
    return spec.response_model.model_validate(response_payload).model_dump()


def _bridge_direct_result(spec: FLToolSpec, request: FLToolRequest) -> dict[str, object]:
    bridge = DEFAULT_BRIDGE
    payload = _payload_from_request(request)
    result = bridge.execute_operation(
        domain=spec.domain,
        operation=spec.operation,
        payload=payload,
        provider=_bridge_provider_hint(request),
    )
    response_payload: dict[str, object] = _build_response_payload(spec, result)
    if spec.task:
        record = _persist_runtime_task(
            spec,
            request,
            provider=result.provider,
            bridge_mode=result.bridge_mode,
            execution_id=result.execution_id,
            message=result.message,
            result=result.result,
        )
        task_id = (
            record.id
            if record is not None
            else str(
                result.result.get("job_id")
                or result.result.get("analysis_id")
                or result.result.get("task_id")
                or result.execution_id
                or f"{spec.name}-{uuid4().hex[:12]}"
            )
        )
        task_result = dict(record.result) if record is not None else dict(result.result)
        response_payload["execution_id"] = task_id
        response_payload["result"] = task_result
        response_payload["task"] = {
            "id": task_id,
            "state": (
                record.state
                if record is not None
                else str(result.result.get("task_status", "queued"))
            ),
            "progress": _result_progress(task_result.get("progress", 0.0)),
            "kind": record.kind if record is not None else spec.domain,
            "artifact_uri": (
                _task_record_artifact_uri(record)
                if record is not None
                else cast(str | None, result.result.get("artifact_uri"))
            ),
            "error": task_result.get("error"),
            "result": task_result,
        }
    return spec.response_model.model_validate(response_payload).model_dump()


def _transaction_result(spec: FLToolSpec, request: FLToolRequest) -> dict[str, object]:
    if spec.response_model is FLTaskToolResponse:
        return _runtime_task_result(spec, request)

    from fl_mcp.transactions.apply import apply_changes as apply_engine

    payload = _payload_from_request(request)
    envelope = TransactionEnvelope(
        request_id=f"{spec.name}-{uuid4().hex[:12]}",
        mode="apply",
        metadata={"tool": spec.name},
        changes=[
            DomainChange(
                domain=spec.domain,
                operation=spec.operation,
                rollback_class=cast(RollbackClass, spec.rollback_class),
                provider=_provider_hint(spec, request),
                payload=payload,
            )
        ],
    )
    result = apply_engine(envelope)
    _bridge_mode = DEFAULT_BRIDGE.mode
    response_payload: dict[str, object] = {
        "status": result.status,
        "tool": spec.name,
        "domain": spec.domain,
        "operation": spec.operation,
        "bridge_mode": _bridge_mode,
        "transaction": result.model_dump(),
    }
    if _bridge_mode == "mock":
        response_payload["mock_mode_warning"] = (
            "This operation was simulated — no real FL Studio state was modified."
        )
    return spec.response_model.model_validate(response_payload).model_dump()


def _make_handler(spec: FLToolSpec) -> Callable[[FLToolRequest], dict[str, object]]:
    def handler(request: FLToolRequest) -> dict[str, object]:
        validated = spec.request_model.model_validate(request)
        if spec.execution_mode == "read":
            return _bridge_read_result(spec, validated)
        if spec.execution_mode == "direct":
            return _bridge_direct_result(spec, validated)
        return _transaction_result(spec, validated)

    handler.__name__ = spec.name
    handler.__qualname__ = spec.name
    handler.__doc__ = spec.description
    handler.__annotations__ = {
        "request": spec.request_model,
        "return": dict[str, object],
    }
    return handler


FL_TOOL_HANDLERS: dict[str, Callable[[FLToolRequest], dict[str, object]]] = {
    spec.name: _make_handler(spec) for spec in FL_TOOL_SPECS
}
for _spec_item in FL_TOOL_SPECS:
    if is_plugin_profile_operation(_spec_item.domain, _spec_item.operation):
        FL_TOOL_HANDLERS[_spec_item.name] = make_plugin_profile_handler(_spec_item)


@functools.cache
def capability_catalog() -> dict[str, object]:
    """Return the full FL tool capability catalog including providers and domains."""
    return {
        "providers": PROVIDER_MATRIX,
        "tools": [spec.model_dump() for spec in FL_TOOL_SPECS],
        "domains": sorted({spec.domain for spec in FL_TOOL_SPECS}),
    }


@functools.lru_cache(maxsize=32)
def domain_capability_catalog(domain: str) -> dict[str, object]:
    """Return the capability catalog filtered to a single FL Studio domain.

    Args:
        domain: The FL Studio domain to filter on (e.g. "mixer", "transport").

    Returns:
        Dict with domain name, matching providers, and tool specs.
    """
    domain_specs = [spec.model_dump() for spec in FL_TOOL_SPECS if spec.domain == domain]
    return {
        "domain": domain,
        "providers": {
            name: provider
            for name, provider in PROVIDER_MATRIX.items()
            if domain in cast(list[str], provider["supported_domains"])
        },
        "tools": domain_specs,
    }
