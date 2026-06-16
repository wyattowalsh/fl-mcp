"""Typed request/response schemas for the explicit FL Studio MCP tool surface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fl_mcp.schemas._types import TaskState

ProviderPreference = str
LoopMode = Literal["song", "pattern"]
ExportFormat = Literal["wav", "mp3", "flac", "ogg"]
UIWindowName = Literal[
    "mixer",
    "channel-rack",
    "piano-roll",
    "playlist",
    "browser",
    "plugin-picker",
]
PlaylistClipMode = Literal["insert", "replace"]

# Request class conventions:
# - Domain base classes (ChannelRequest, MixerRequest, etc.) use domain-prefixed
#   field names (channel_index, track_index) with Field(ge=0) validation.
#   Used for complex mutation operations.
# - Granular per-property classes inherit FLToolRequest directly with a plain
#   `index: int = 0` field. Used for simple get/set property operations.


class FLToolRequest(BaseModel):
    """Shared request metadata for explicit FL Studio tool handlers."""

    provider: ProviderPreference = Field(default="auto", min_length=1)
    session_label: str | None = None


class EmptyFLToolRequest(FLToolRequest):
    """Request carrying only shared provider metadata and no extra fields."""


class ConnectionConnectRequest(FLToolRequest):
    """Request to configure FL Studio bridge input/output ports."""

    input_port: str | None = None
    output_port: str | None = None


class MidiSendNoteRequest(FLToolRequest):
    """Request to send a MIDI note message."""

    port: str | None = None
    channel: int = Field(default=0, ge=0, le=15)
    note: int = Field(ge=0, le=127)
    velocity: int = Field(default=100, ge=0, le=127)
    duration_beats: float = Field(default=1.0, gt=0)
    position_beats: float | None = Field(default=None, ge=0)


class MidiControlChangeRequest(FLToolRequest):
    """Request to send a MIDI control-change message."""

    port: str | None = None
    channel: int = Field(default=0, ge=0, le=15)
    control: int = Field(ge=0, le=127)
    value: int = Field(ge=0, le=127)


class MidiProgramChangeRequest(FLToolRequest):
    """Request to send a MIDI program-change message."""

    port: str | None = None
    channel: int = Field(default=0, ge=0, le=15)
    program: int = Field(ge=0, le=127)


class MidiPitchBendRequest(FLToolRequest):
    """Request to send a MIDI pitch-bend message."""

    port: str | None = None
    channel: int = Field(default=0, ge=0, le=15)
    value: int = Field(ge=-8192, le=8191)


class TransportTempoRequest(FLToolRequest):
    """Request to set the project tempo in BPM."""

    bpm: float = Field(gt=0, le=400)


class TransportPositionRequest(FLToolRequest):
    """Request to set the transport song position in beats."""

    position_beats: float = Field(ge=0)


class TransportLengthRequest(FLToolRequest):
    """Request to read the song or pattern length."""

    mode: LoopMode = "song"


class TransportLoopModeRequest(FLToolRequest):
    """Request to switch between song and pattern loop modes."""

    mode: LoopMode


class TransportPlaybackSpeedRequest(FLToolRequest):
    """Request to adjust the FL Studio playback speed multiplier."""

    speed: float = Field(gt=0, le=4)


class MixerTrackRequest(FLToolRequest):
    """Request targeting a single mixer track by index."""

    track_index: int = Field(ge=0)


class MixerTrackUpdateRequest(MixerTrackRequest):
    """Request to update one or more mixer track properties."""

    volume: float | None = Field(default=None, ge=0, le=1)
    pan: float | None = Field(default=None, ge=-1, le=1)
    name: str | None = None
    color: int | None = Field(default=None, ge=0)
    muted: bool | None = None
    solo: bool | None = None
    armed: bool | None = None


class MixerStereoSeparationRequest(MixerTrackRequest):
    """Request to set stereo separation on a mixer track."""

    stereo_separation: float = Field(ge=-1, le=1)


class ChannelRequest(FLToolRequest):
    """Request targeting a single channel rack channel by index."""

    channel_index: int = Field(ge=0)


class ChannelSelectRequest(ChannelRequest):
    """Request to select a channel, optionally deselecting others."""

    exclusive: bool = False


class ChannelUpdateRequest(ChannelRequest):
    """Request to update one or more channel rack channel properties."""

    volume: float | None = Field(default=None, ge=0, le=1)
    pan: float | None = Field(default=None, ge=-1, le=1)
    name: str | None = None
    color: int | None = Field(default=None, ge=0)
    muted: bool | None = None
    solo: bool | None = None


class ChannelRouteRequest(ChannelRequest):
    """Request to route a channel to a specific mixer track."""

    mixer_track_index: int = Field(ge=0)


class ChannelStepSequenceRequest(ChannelRequest):
    """Request to set step-sequencer state for a channel."""

    steps: list[int] = Field(default_factory=list)


class ChannelTriggerNoteRequest(ChannelRequest):
    """Request to trigger a note on a channel."""

    note: int = Field(ge=0, le=127)
    velocity: int = Field(default=100, ge=0, le=127)
    duration_beats: float = Field(default=1.0, gt=0)


class ChannelPitchRequest(ChannelRequest):
    """Request to set the pitch offset of a channel in cents."""

    pitch: float = Field(ge=-1200, le=1200)


class PatternRequest(FLToolRequest):
    """Request targeting a single pattern by index."""

    pattern_index: int = Field(ge=0)


class PatternCreateRequest(FLToolRequest):
    """Request to create a new pattern with a given name."""

    name: str = Field(min_length=1)


class PatternRenameRequest(PatternRequest):
    """Request to rename an existing pattern."""

    name: str = Field(min_length=1)


class PatternLengthRequest(PatternRequest):
    """Request to set the length of a pattern in beats."""

    length_beats: float = Field(gt=0)


class PlaylistTrackRequest(FLToolRequest):
    """Request targeting a single playlist track by index."""

    track_index: int = Field(ge=0)


class PlaylistTrackUpdateRequest(PlaylistTrackRequest):
    """Request to rename a playlist track."""

    name: str = Field(min_length=1)


class PlaylistArrangementRequest(FLToolRequest):
    """Request targeting a playlist arrangement by index."""

    arrangement_index: int = Field(default=0, ge=0)


class PlaylistClipRequest(PlaylistArrangementRequest):
    """Request targeting a playlist clip by arrangement and track."""

    clip_id: str | None = None
    track_index: int = Field(default=0, ge=0)


class PlaylistPlaceClipRequest(PlaylistClipRequest):
    """Request to place a clip into a playlist arrangement."""

    source: str = Field(min_length=1)
    start_beats: float = Field(ge=0)
    length_beats: float = Field(gt=0)
    mode: PlaylistClipMode = "insert"


class PlaylistMoveClipRequest(PlaylistClipRequest):
    """Request to move a playlist clip to a new position."""

    destination_track_index: int = Field(ge=0)
    destination_start_beats: float = Field(ge=0)


class PlaylistMarkerRequest(PlaylistArrangementRequest):
    """Request targeting a playlist marker by arrangement."""

    marker_id: str | None = None


class PlaylistCreateMarkerRequest(PlaylistMarkerRequest):
    """Request to create a named marker in the playlist arrangement."""

    name: str = Field(min_length=1)
    position_beats: float = Field(ge=0)


class PlaylistUpdateMarkerRequest(PlaylistMarkerRequest):
    """Request to update properties of a playlist marker."""

    name: str | None = None
    position_beats: float | None = Field(default=None, ge=0)


class PianoRollNote(BaseModel):
    """Single piano-roll note with pitch, velocity, length, and position."""

    note: int = Field(ge=0, le=127)
    velocity: int = Field(default=100, ge=0, le=127)
    length_beats: float = Field(default=1.0, gt=0)
    position_beats: float = Field(default=0, ge=0)


class PianoRollNotesRequest(FLToolRequest):
    """Request to append or replace piano-roll notes."""

    notes: list[PianoRollNote] = Field(default_factory=list)
    mode: Literal["append", "replace"] = "append"


class PianoRollDeleteNotesRequest(FLToolRequest):
    """Request to delete specific piano-roll notes."""

    notes: list[PianoRollNote] = Field(default_factory=list)


class PianoRollQuantizeRequest(FLToolRequest):
    """Request to quantize piano-roll notes to a rhythmic grid."""

    grid_beats: float = Field(default=0.25, gt=0)
    strength: float = Field(default=1.0, ge=0, le=1)


class PianoRollTransposeRequest(FLToolRequest):
    """Request to transpose piano-roll notes by semitones."""

    semitones: int = Field(ge=-48, le=48)


class PianoRollHumanizeRequest(FLToolRequest):
    """Request to humanize timing and velocity of piano-roll notes."""

    timing_strength: float = Field(default=0.15, ge=0, le=1)
    velocity_strength: float = Field(default=0.1, ge=0, le=1)
    seed: int = Field(default=0, ge=0)


class PianoRollGenerateRequest(FLToolRequest):
    """Base request for piano-roll generative operations."""

    key: str = Field(default="C")
    scale: str = Field(default="major")
    bars: int = Field(default=4, ge=1, le=64)
    seed: int = Field(default=0, ge=0)


class PianoRollGenerateChordRequest(PianoRollGenerateRequest):
    """Request to generate chord notes in the piano roll."""

    progression: list[str] = Field(default_factory=list)


class PianoRollGenerateMelodyRequest(PianoRollGenerateRequest):
    """Request to generate a melody in the piano roll."""

    density: float = Field(default=0.6, ge=0, le=1)


class PianoRollGenerateBassRequest(PianoRollGenerateRequest):
    """Request to generate a bass line in the piano roll."""

    octave: int = Field(default=3, ge=0, le=8)


class PluginSlotRequest(ChannelRequest):
    """Request targeting a plugin slot on a channel."""

    plugin_slot: int | None = Field(default=None, ge=0)


class PluginParameterRequest(PluginSlotRequest):
    """Request to read a single plugin parameter by name."""

    parameter: str = Field(min_length=1)


class PluginSetParameterRequest(PluginParameterRequest):
    """Request to set a plugin parameter to a normalized value."""

    value: float = Field(ge=0, le=1)


class PluginParameterIndexRequest(PluginSlotRequest):
    """Request to read a plugin parameter by FL wrapper parameter index."""

    parameter_index: int = Field(default=0, ge=0)


class PluginLoadRequest(PluginSlotRequest):
    """Request to load a plugin into a channel slot."""

    plugin_name: str = Field(min_length=1)


class PluginReplaceRequest(PluginLoadRequest):
    """Request to replace the plugin currently loaded in a slot."""

    replace_current: bool = True


class PluginWindowRequest(PluginSlotRequest):
    """Request to show or hide a plugin window."""

    visible: bool = True


class UIWindowRequest(FLToolRequest):
    """Request targeting a named FL Studio window."""

    window: UIWindowName


class UIShowWindowRequest(UIWindowRequest):
    """Request to show or hide a named FL Studio window."""

    visible: bool = True


class ProjectPathRequest(FLToolRequest):
    """Request specifying an FL Studio project file path."""

    path: str = Field(min_length=1)


class RenderJobRequest(FLToolRequest):
    """Request to query or cancel a render job by ID."""

    job_id: str = Field(min_length=1)


class RenderExportRequest(FLToolRequest):
    """Request to start a render/export task."""

    output_path: str | None = None
    format: ExportFormat = "wav"
    tail_seconds: float = Field(default=0, ge=0)


class AudioAnalyzeRequest(FLToolRequest):
    """Request to start an audio analysis task."""

    input_path: str | None = None
    analyzer: str = "spectrum"


class AudioAnalysisRequest(FLToolRequest):
    """Request to query or cancel an audio analysis task by ID."""

    analysis_id: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Channels domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class ChannelColorRequest(FLToolRequest):
    """Request to read or set the color of a channel rack channel."""

    index: int = Field(default=0, ge=0)
    color: int | None = Field(default=None, ge=0)  # None = read, int = set


class ChannelVolumeRequest(FLToolRequest):
    """Request to read or set the volume of a channel (0.0-1.0)."""

    index: int = Field(default=0, ge=0)
    volume: float | None = Field(default=None, ge=0, le=1)  # None = read, float = set


class ChannelPanRequest(FLToolRequest):
    """Request to read or set the pan position of a channel (-1.0 to 1.0)."""

    index: int = Field(default=0, ge=0)
    pan: float | None = Field(default=None, ge=-1, le=1)  # None = read, float = set


class ChannelMuteRequest(FLToolRequest):
    """Request to toggle or set the mute state of a channel."""

    index: int = Field(default=0, ge=0)
    value: int = Field(default=-1, ge=-1, le=1)  # -1 = toggle


class ChannelSoloRequest(FLToolRequest):
    """Request to solo a channel rack channel."""

    index: int = Field(default=0, ge=0)


class ChannelGridBitRequest(FLToolRequest):
    """Request to read or set a step-sequencer grid bit for a channel."""

    index: int = Field(default=0, ge=0)
    position: int = Field(default=0, ge=0)
    value: bool | None = None  # None = read, bool = set


class ChannelQuickQuantizeRequest(FLToolRequest):
    """Request to quick-quantize note positions for a channel."""

    index: int = Field(default=0, ge=0)
    start_only: int = Field(default=1, ge=0, le=1)


class ChannelLoadSampleRequest(FLToolRequest):
    """Request to load a sample file into a channel rack channel."""

    channel_index: int = Field(ge=0)
    file_path: str = Field(min_length=1)
    bank: int | None = Field(default=None, ge=0)
    program: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Mixer domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class MixerTrackColorRequest(FLToolRequest):
    """Request to read or set the color of a mixer track."""

    index: int = Field(default=0, ge=0)
    color: int | None = Field(default=None, ge=0)


class MixerTrackVolumeRequest(FLToolRequest):
    """Request to read or set the volume of a mixer track."""

    index: int = Field(default=0, ge=0)
    volume: float | None = Field(default=None, ge=0, le=1)


class MixerTrackPanRequest(FLToolRequest):
    """Request to read or set the pan position of a mixer track."""

    index: int = Field(default=0, ge=0)
    pan: float | None = Field(default=None, ge=-1, le=1)


class MixerMuteTrackRequest(FLToolRequest):
    """Request to toggle or set the mute state of a mixer track."""

    index: int = Field(default=0, ge=0)
    value: int = Field(default=-1, ge=-1, le=1)


class MixerSoloTrackRequest(FLToolRequest):
    """Request to solo a mixer track."""

    index: int = Field(default=0, ge=0)
    value: int = Field(default=-1, ge=-1, le=1)


class MixerArmTrackRequest(FLToolRequest):
    """Request to arm a mixer track for recording."""

    index: int = Field(default=0, ge=0)


class MixerRouteToRequest(FLToolRequest):
    """Request to set or clear a routing connection between mixer tracks."""

    index: int = Field(default=0, ge=0)
    dest_index: int = Field(default=0, ge=0)
    value: bool = True


class MixerRouteSendLevelRequest(FLToolRequest):
    """Request to read or set the send level for a mixer routing connection."""

    index: int = Field(default=0, ge=0)
    dest_index: int = Field(default=0, ge=0)
    level: float | None = Field(default=None, ge=0, le=1)


class MixerEqGainRequest(FLToolRequest):
    """Request to read or set the EQ gain for a band on a mixer track."""

    index: int = Field(default=0, ge=0)
    band: int = Field(default=0, ge=0)
    value: float | None = None


class MixerEqFrequencyRequest(FLToolRequest):
    """Request to read or set the EQ frequency for a band on a mixer track."""

    index: int = Field(default=0, ge=0)
    band: int = Field(default=0, ge=0)
    value: float | None = Field(default=None, ge=0)


class MixerEqBandwidthRequest(FLToolRequest):
    """Request to read the EQ bandwidth for a band on a mixer track."""

    index: int = Field(default=0, ge=0)
    band: int = Field(default=0, ge=0)


class MixerSlotRequest(FLToolRequest):
    """Request targeting a specific mixer track effect slot."""

    track_index: int = Field(ge=0)
    slot_index: int = Field(ge=0)


class MixerSlotEnableRequest(FLToolRequest):
    """Request to enable or disable a mixer track effect slot."""

    track_index: int = Field(ge=0)
    slot_index: int = Field(ge=0)
    enabled: bool


class MixerSetSlotPluginRequest(FLToolRequest):
    """Request to set the plugin for a mixer track effect slot."""

    track_index: int = Field(ge=0)
    slot_index: int = Field(ge=0)
    plugin_name: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Patterns domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class PatternColorRequest(FLToolRequest):
    """Request to read or set the color of a pattern."""

    index: int = Field(default=0, ge=0)
    color: int | None = Field(default=None, ge=0)


class PatternCloneRequest(FLToolRequest):
    """Request to clone an existing pattern."""

    index: int | None = Field(default=None, ge=0)


class PatternJumpToRequest(FLToolRequest):
    """Request to jump to a specific pattern by index."""

    index: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Playlist domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class PlaylistTrackColorRequest(FLToolRequest):
    """Request to read or set the color of a playlist track."""

    index: int = Field(default=0, ge=0)
    color: int | None = Field(default=None, ge=0)


class PlaylistMuteTrackRequest(FLToolRequest):
    """Request to toggle or set the mute state of a playlist track."""

    index: int = Field(default=0, ge=0)
    value: int = Field(default=-1, ge=-1, le=1)


class PlaylistSoloTrackRequest(FLToolRequest):
    """Request to solo a playlist track."""

    index: int = Field(default=0, ge=0)
    value: int = Field(default=-1, ge=-1, le=1)


class PlaylistSelectTrackRequest(FLToolRequest):
    """Request to select a playlist track."""

    index: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Transport domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class TransportRewindRequest(FLToolRequest):
    """Request to rewind the transport position."""

    start_stop: int = Field(default=1, ge=0, le=1)


class TransportFastForwardRequest(FLToolRequest):
    """Request to fast-forward the transport position."""

    start_stop: int = Field(default=1, ge=0, le=1)


class TransportMarkerJumpRequest(FLToolRequest):
    """Request to jump to the next or previous marker."""

    value: int = 1


class TransportTimeSignatureRequest(FLToolRequest):
    """Request to set the project time signature."""

    numerator: int = Field(ge=1)
    denominator: int = Field(ge=1)


class TransportSwingRequest(FLToolRequest):
    """Request to set the transport swing amount."""

    value: float = Field(ge=0, le=1)


# ---------------------------------------------------------------------------
# Plugins domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class PluginParamValueStringRequest(FLToolRequest):
    """Request to read the string representation of a plugin parameter."""

    param_index: int = Field(default=0, ge=0)
    index: int = Field(default=0, ge=0)
    slot_index: int = -1


class PluginColorRequest(FLToolRequest):
    """Request to read the color of a plugin instance."""

    index: int = Field(default=0, ge=0)
    slot_index: int = -1


class PluginPadInfoRequest(FLToolRequest):
    """Request to read performance-pad information for a plugin."""

    chan_index: int = Field(default=0, ge=0)
    slot_index: int = -1
    param_option: int = 0
    param_index: int = -1


class PluginPresetNameRequest(FLToolRequest):
    """Request targeting a plugin preset by name."""

    channel_index: int = Field(ge=0)
    preset_name: str = Field(min_length=1)


class PluginInventoryScanRequest(FLToolRequest):
    """Request to scan local plugin bundles, FL plugin database entries, and presets."""

    query: str | None = None
    include_presets: bool = True
    include_paths: bool = False
    rescan: bool = False
    limit: int = Field(default=100, ge=1, le=500)


class PluginProfileListRequest(FLToolRequest):
    """Request to list built-in and local plugin profiles."""

    query: str | None = None
    status: str | None = None
    include_inventory: bool = True
    limit: int = Field(default=100, ge=1, le=500)


class PluginProfileRequest(FLToolRequest):
    """Request to read one plugin profile and its local state."""

    profile_id: str = Field(min_length=1)
    include_inventory: bool = True
    include_calibration: bool = True


class PluginProfileResolveRequest(FLToolRequest):
    """Request to resolve a plugin query to profile/inventory candidates."""

    query: str = Field(min_length=1)
    limit: int = Field(default=25, ge=1, le=100)


class PluginProfileInstanceRequest(FLToolRequest):
    """Request targeting a plugin instance for probing or semantic control mapping."""

    profile_id: str | None = None
    channel_index: int = Field(default=0, ge=0)
    plugin_slot: int | None = Field(default=None, ge=0)
    plugin_format: str | None = None
    fingerprint: str | None = None


class PluginEnumerateParametersRequest(PluginProfileInstanceRequest):
    """Request to enumerate FL-exposed parameters for a plugin instance."""

    include_values: bool = True
    include_value_strings: bool = True
    cursor: int = Field(default=0, ge=0)
    max_parameters: int = Field(default=256, ge=1, le=4096)
    timeout_ms: int = Field(default=5000, ge=100, le=60000)


class PluginGenerateRawProfileRequest(PluginEnumerateParametersRequest):
    """Request to preview a raw profile from live parameter enumeration."""

    profile_id: str | None = None


class PluginCalibrationWriteRequest(PluginProfileInstanceRequest):
    """Request to persist a local semantic-control calibration overlay."""

    profile_id: str = Field(min_length=1)
    mapped_controls: dict[str, int] = Field(default_factory=dict)
    fl_reported_name: str | None = None
    parameter_count: int | None = Field(default=None, ge=0)
    persist: bool = True


class PluginPrioritySupportAuditRequest(FLToolRequest):
    """Request to audit priority plugin support states."""

    query: str | None = None
    include_paths: bool = False
    include_p3: bool = True
    fail_on_missing_priority: bool = False


class PluginProfileLearnRequest(PluginProfileInstanceRequest):
    """Request to learn or preview a local parameter mapping for a semantic control."""

    profile_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)
    observed_parameter_index: int | None = Field(default=None, ge=0)
    value: float | None = Field(default=None, ge=0, le=1)


class PluginProfileValidateRequest(FLToolRequest):
    """Request to validate profile, inventory, and calibration readiness."""

    profile_id: str = Field(min_length=1)
    plugin_format: str | None = None
    fingerprint: str | None = None


class PluginProfileVerifyRequest(PluginProfileInstanceRequest):
    """Request to verify calibrated semantic controls on a plugin instance."""

    profile_id: str = Field(min_length=1)


class PluginMappedParameterRequest(PluginProfileInstanceRequest):
    """Request to read a semantic plugin control via a calibrated FL parameter index."""

    profile_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)


class PluginSetMappedParameterRequest(PluginMappedParameterRequest):
    """Request to set a semantic plugin control through a calibrated FL parameter index."""

    value: float | int | str


class PluginProfilePresetRequest(PluginProfileInstanceRequest):
    """Request to load a profile-scoped preset, bank, or wrapper-state asset."""

    profile_id: str = Field(min_length=1)
    preset_name: str | None = None
    preset_path: str | None = None


class PluginLocalPresetsRequest(FLToolRequest):
    """Request to list local plugin preset, bank, and wrapper-state assets."""

    query: str | None = None
    profile_id: str | None = None
    include_paths: bool = False
    limit: int = Field(default=100, ge=1, le=500)


class PluginReconcileInventoryRequest(FLToolRequest):
    """Request to summarize mismatches between installed bundles, FL database, and profiles."""

    query: str | None = None
    include_presets: bool = True
    include_paths: bool = False


# ---------------------------------------------------------------------------
# UI domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class UIWindowIndexRequest(FLToolRequest):
    """Request targeting an FL Studio window by numeric index."""

    index: int = Field(default=0, ge=0)


class UIScrollWindowRequest(FLToolRequest):
    """Request to scroll an FL Studio window by an offset."""

    index: int = Field(default=0, ge=0)
    value: int = 0
    direction_flag: int = 0


class UISnapModeRequest(FLToolRequest):
    """Request to read or set the FL Studio UI snap mode."""

    value: int | None = None  # None = get, int = set


class UIHintMsgRequest(FLToolRequest):
    """Request to read or set the FL Studio toolbar hint message."""

    msg: str | None = None  # None = get, str = set


# ---------------------------------------------------------------------------
# General domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class GeneralSaveUndoRequest(FLToolRequest):
    """Request to save an undo checkpoint with a descriptive name."""

    undo_name: str = "MCP operation"
    flags: int = 0


class GeneralNewProjectRequest(FLToolRequest):
    """Request to create a new FL Studio project, discarding the current one."""

    save_current: bool = False


# ---------------------------------------------------------------------------
# Device domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class DeviceMidiOutMsgRequest(FLToolRequest):
    """Request to send a raw MIDI output message through the device module."""

    message: int = 0
    channel: int = -1
    data1: int = -1
    data2: int = -1


class DeviceMidiOutSysexRequest(FLToolRequest):
    """Request to send a SysEx message through the device module."""

    message: str = ""  # hex-encoded bytes


# ---------------------------------------------------------------------------
# Arrangement domain - new FL Studio API surface models
# ---------------------------------------------------------------------------


class ArrangementTimeRequest(FLToolRequest):
    """Request to read the current time position in the arrangement."""

    snap: int = 0


class ArrangementTimeHintRequest(FLToolRequest):
    """Request to read a formatted time hint for the arrangement."""

    mode: int = 0
    time: int = 0


class ArrangementJumpToMarkerRequest(FLToolRequest):
    """Request to jump to the next or previous arrangement marker."""

    delta: int = 1
    select: bool = False


# ---------------------------------------------------------------------------
# Automation domain - FL Studio automation clip models
# ---------------------------------------------------------------------------


class AutomationClipRequest(FLToolRequest):
    clip_index: int = Field(ge=0)


class AutomationCreateRequest(FLToolRequest):
    name: str
    channel_index: int | None = Field(default=None, ge=0)


class AutomationWritePointsRequest(FLToolRequest):
    clip_index: int = Field(ge=0)
    points: list[dict[str, object]]


class AutomationLinkRequest(FLToolRequest):
    clip_index: int = Field(ge=0)
    target_type: Literal["mixer", "channel", "plugin"]
    target_index: int = Field(ge=0)
    parameter_index: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class FLTaskInfo(BaseModel):
    """Progress and result metadata for an asynchronous FL Studio task."""

    id: str
    state: TaskState
    progress: float = Field(default=0, ge=0, le=1)
    kind: str
    artifact_uri: str | None = None
    error: str | None = None
    result: dict[str, object] = Field(default_factory=dict)


class _FLToolResponseBase(BaseModel):
    """Private base carrying fields common to every FL tool response."""

    tool: str
    domain: str
    operation: str
    mock_mode_warning: str | None = None


class FLToolExecutionResponse(_FLToolResponseBase):
    """Response from a direct or read FL Studio tool execution."""

    status: Literal["ok", "error"]
    provider: str
    bridge_mode: str
    execution_id: str | None = None
    message: str
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None


class FLTaskToolResponse(_FLToolResponseBase):
    """Response from an asynchronous FL Studio task tool (render, analysis)."""

    status: Literal["ok", "error"]
    provider: str
    bridge_mode: str
    execution_id: str | None = None
    message: str
    task: FLTaskInfo
    error_code: str | None = None


class FLTransactionToolResponse(_FLToolResponseBase):
    """Response from a transaction-mode FL Studio tool execution."""

    status: Literal["planned", "applied", "failed", "partially_applied"]
    bridge_mode: str = "mock"
    transaction: dict[str, object]
