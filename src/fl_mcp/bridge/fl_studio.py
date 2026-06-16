"""FL Studio bridge adapters with live subprocess + deterministic mock fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Literal

from fl_mcp.bridge.live_surface import forced_live_flapi_supports
from fl_mcp.bridge.mock_generators import _MOCK_DISPATCH, mock_result
from fl_mcp.graph.domains import DOMAINS
from fl_mcp.schemas import DomainChange, RollbackClass
from fl_mcp.schemas.bridge import BridgeLiveRequest, BridgeLiveResponse

logger = logging.getLogger(__name__)

BridgeMode = Literal["mock", "live"]
DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS = 20.0
LIVE_BRIDGE_TIMEOUT_ENV = "FL_MCP_FL_STUDIO_BRIDGE_TIMEOUT_SECONDS"

# INFORMATIONAL ONLY - not used as the mock guard. _MOCK_DISPATCH is the source of truth.
_SUPPORTED_OPERATIONS_BY_DOMAIN: dict[str, set[str]] = {
    "connection": {"connect", "status"},
    "midi": {"list_ports", "send_cc", "send_note", "send_pitch_bend", "send_program_change"},
    "transport": {
        "get_length",
        "get_playback_state",
        "get_song_position",
        "get_state",
        "get_tempo",
        "pause",
        "play",
        "record",
        "set_loop_mode",
        "set_playback_speed",
        "set_song_position",
        "set_tempo",
        "stop",
    },
    "mixer": {
        "get_track",
        "get_track_info",
        "list_tracks",
        "get_track_count",
        "get_meter_level",
        "mute",
        "set_name",
        "set_pan",
        "set_stereo_separation",
        "set_volume",
        "solo",
        "update_track",
    },
    "channels": {
        "duplicate",
        "get_channel",
        "get_info",
        "get_selected",
        "get_step_sequence",
        "get_target_fx_track",
        "list",
        "list_channels",
        "mute",
        "route_to_mixer",
        "select_channel",
        "set_pan",
        "set_pitch",
        "set_step_sequence",
        "set_volume",
        "solo",
        "trigger_note",
        "update_channel",
    },
    "patterns": {
        "create",
        "create_pattern",
        "list",
        "list_patterns",
        "rename",
        "rename_pattern",
        "select",
        "select_pattern",
        "set_length",
    },
    "playlist": {
        "create_marker",
        "delete_clip",
        "delete_marker",
        "get_arrangement",
        "get_track",
        "get_track_info",
        "list_clips",
        "list_markers",
        "list_tracks",
        "move_clip",
        "place_clip",
        "set_track_name",
        "update_marker",
        "update_track",
    },
    "piano-roll": {
        "clear",
        "delete_notes",
        "generate_bass",
        "generate_chords",
        "generate_melody",
        "get_state",
        "humanize",
        "quantize",
        "send_notes",
        "transpose",
    },
    "plugins": {
        "get_name",
        "get_parameter",
        "get_parameter_count",
        "get_parameter_name",
        "get_param_value_string",
        "get_param_value",
        "get_parameters",
        "get_preset_name",
        "get_preset_count",
        "is_valid",
        "list_params",
        "list_plugins",
        "load",
        "load_preset_by_name",
        "next_preset",
        "prev_preset",
        "previous_preset",
        "replace",
        "set_parameter",
        "set_param_value",
        "show_window",
    },
    "ui": {"get_visibility", "get_visible", "show_window"},
    "general": {
        "get_project_path",
        "get_project_state",
        "get_project_title",
        "get_version",
        "open_project",
        "redo",
        "save_project",
        "save_project_as",
        "undo",
    },
    "render": {"cancel_job", "export", "get_job"},
    "audio": {"analyze", "cancel_analysis", "get_analysis"},
    "device": {"is_assigned", "get_name", "get_port_number", "midi_out_msg", "midi_out_sysex"},
    "arrangement": {
        "get_current_time",
        "get_time_hint",
        "get_selection_start",
        "get_selection_end",
        "jump_to_marker",
    },
}

_PROVIDER_ALIASES: dict[str, str] = {
    "flapi": "flapi-live",
    "flapi-live": "flapi-live",
    "midi-script": "piano-roll-script",
    "midi-script-live": "piano-roll-script",
    "piano-roll-script": "piano-roll-script",
    "midi-fallback": "midi-fallback",
    "mock": "mock",
}


def default_provider_for_operation(domain: str, operation: str | None = None) -> str:
    """Return the canonical provider name for a given domain and optional operation.

    Args:
        domain: FL Studio domain identifier (e.g. ``"mixer"``, ``"transport"``).
        operation: Optional operation name to check for provider overrides.

    Returns:
        Resolved provider string, defaulting to ``"mock"`` when no shipped live
        or fallback provider covers the operation.
    """
    runtime_mode = os.getenv("FL_MCP_BRIDGE_MODE", "mock").strip().lower()
    if runtime_mode == "live" and (
        operation is None or forced_live_flapi_supports(domain, operation)
    ):
        return "flapi-live"
    return "mock"


@dataclass(slots=True, frozen=True)
class BridgeExecutionResult:
    """Immutable result of a single bridge operation execution."""

    domain: str
    operation: str
    success: bool
    message: str
    error_code: str | None
    execution_id: str | None
    bridge_mode: BridgeMode
    provider: str
    result: dict[str, object]


class FLStudioBridge:
    """Executes domain operations against a live bridge command or deterministic mock.

    Trust boundary
    --------------
    * The bridge command (``FL_MCP_FL_STUDIO_BRIDGE_CMD`` env var) is treated as
      **trusted operator input** — it is parsed with :func:`shlex.split` and
      passed directly as the *argv* list to :func:`subprocess.run`.
    * The operation payload is serialised with :func:`json.dumps` and appended as
      a single positional argument, so it cannot inject additional shell tokens.
    * ``subprocess.run`` is called **without** ``shell=True`` (the default),
      meaning no shell expansion or interpretation occurs on the command line.
    * Callers must ensure ``live_command`` is non-empty when ``mode="live"``;
      the bridge validates this before every live execution and returns a clear
      error result when the invariant is violated.
    """

    def __init__(
        self,
        *,
        mode: BridgeMode = "mock",
        live_command: str | None = None,
        live_timeout_seconds: float = DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS,
    ) -> None:
        self.mode = mode
        self.live_command = live_command
        self.live_timeout_seconds = live_timeout_seconds
        if self.mode == "live" and (not self.live_command or not self.live_command.strip()):
            logger.warning("Live mode configured but FLSTUDIO_LIVE_COMMAND is empty or whitespace")

    @classmethod
    def from_environment(cls) -> FLStudioBridge:
        """Construct a bridge instance from environment variables.

        Reads ``FL_MCP_BRIDGE_MODE``, ``FL_MCP_FL_STUDIO_BRIDGE_CMD``, and
        ``FL_MCP_FL_STUDIO_BRIDGE_TIMEOUT_SECONDS`` from the process
        environment.
        """
        configured_mode = os.getenv("FL_MCP_BRIDGE_MODE", "mock").strip().lower()
        mode: BridgeMode = "live" if configured_mode == "live" else "mock"
        command = os.getenv("FL_MCP_FL_STUDIO_BRIDGE_CMD")
        return cls(
            mode=mode,
            live_command=command,
            live_timeout_seconds=_live_bridge_timeout_seconds_from_environment(),
        )

    def execute_change(self, change: DomainChange) -> BridgeExecutionResult:
        """Execute a domain change through the bridge.

        Args:
            change: Typed domain change carrying domain, operation, payload,
                rollback class, and optional provider hint.
        """
        return self._execute(
            domain=change.domain,
            operation=change.operation,
            payload=change.payload,
            rollback_class=change.rollback_class,
            provider_hint=change.provider,
        )

    def execute_operation(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
        provider: str | None = None,
    ) -> BridgeExecutionResult:
        """Execute a domain operation using explicit parameters.

        Args:
            domain: Target FL Studio domain.
            operation: Operation name within the domain.
            payload: Arbitrary key-value payload forwarded to the bridge.
            provider: Optional provider override; ``None`` uses automatic
                resolution.
        """
        logger.debug(
            "Executing operation domain=%s operation=%s mode=%s",
            domain,
            operation,
            self.mode,
        )
        result = self._execute(
            domain=domain,
            operation=operation,
            payload=payload,
            rollback_class=None,
            provider_hint=provider,
        )
        if not result.success:
            logger.warning(
                "Bridge execution failed: domain=%s operation=%s provider=%s error_code=%s",
                domain,
                operation,
                result.provider,
                result.error_code,
            )
        return result

    def _execute(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
        rollback_class: RollbackClass | None,
        provider_hint: str | None,
    ) -> BridgeExecutionResult:
        requested_provider = provider_hint or payload.get("provider")
        explicit_mock_provider = (
            isinstance(requested_provider, str)
            and requested_provider
            and requested_provider != "auto"
            and _PROVIDER_ALIASES.get(requested_provider, requested_provider) == "mock"
        )
        explicit_non_mock_provider = (
            isinstance(requested_provider, str)
            and requested_provider
            and requested_provider != "auto"
            and _PROVIDER_ALIASES.get(requested_provider, requested_provider) != "mock"
        )
        provider = _resolve_provider(self.mode, domain, operation, payload, provider_hint)
        if domain not in DOMAINS:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=f"Domain '{domain}' is not registered.",
                error_code="unsupported_domain",
                execution_id=None,
                bridge_mode=self.mode,
                provider=provider,
                result={},
            )

        if self.mode == "mock" and explicit_non_mock_provider:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=(
                    f"Provider '{provider}' requires live bridge mode for "
                    f"'{domain}.{operation}'. Request provider='mock' explicitly "
                    "for deterministic rehearsal."
                ),
                error_code="live_provider_unavailable",
                execution_id=None,
                bridge_mode="mock",
                provider=provider,
                result={
                    "required_bridge_mode": "live",
                    "current_bridge_mode": self.mode,
                    "remediation": (
                        "Set FL_MCP_BRIDGE_MODE=live and configure "
                        "FL_MCP_FL_STUDIO_BRIDGE_CMD, or request provider='mock'."
                    ),
                },
            )

        use_mock_backend = self.mode == "mock" or explicit_mock_provider

        if use_mock_backend and not _mock_supports_operation(domain, operation):
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=(
                    f"Mock bridge does not implement '{domain}.{operation}'. "
                    f"Supported mock operations for '{domain}': "
                    f"{', '.join(_supported_operations(domain)) or 'none'}."
                ),
                error_code="unsupported_operation",
                execution_id=None,
                bridge_mode="mock",
                provider=provider,
                result={"supported_operations": _supported_operations(domain)},
            )

        if use_mock_backend:
            return self._execute_mock(
                domain=domain,
                operation=operation,
                payload=payload,
                rollback_class=rollback_class,
                provider=provider,
            )

        if self.mode == "live":
            return self._execute_live(
                domain=domain,
                operation=operation,
                payload=payload,
                rollback_class=rollback_class,
                provider=provider,
            )

        return self._execute_mock(
            domain=domain,
            operation=operation,
            payload=payload,
            rollback_class=rollback_class,
            provider=provider,
        )

    def _execute_live(
        self,
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
        rollback_class: RollbackClass | None,
        provider: str,
    ) -> BridgeExecutionResult:
        if not self.live_command or not self.live_command.strip():
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=(
                    "Live bridge mode requires a non-empty FL_MCP_FL_STUDIO_BRIDGE_CMD. "
                    "Set the environment variable to the bridge executable path."
                ),
                error_code="bridge_process_error",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )

        bridge_request = BridgeLiveRequest(
            domain=domain,
            operation=operation,
            rollback_class=rollback_class,
            provider=provider,
            payload=payload,
        )
        bridge_payload = bridge_request.model_dump()

        try:
            completed = subprocess.run(
                [*shlex.split(self.live_command), json.dumps(bridge_payload, sort_keys=True)],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.live_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=(
                    f"Live bridge command timed out after {self.live_timeout_seconds:g} seconds."
                ),
                error_code="bridge_timeout",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )
        except OSError as exc:
            logger.warning(
                "Bridge process error: domain=%s operation=%s provider=%s: %s",
                domain,
                operation,
                provider,
                exc,
                exc_info=True,
            )
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=str(exc),
                error_code="bridge_process_error",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )

        if completed.returncode != 0:
            decoded, decode_error = _decode_live_bridge_response(completed.stdout)
            if decoded is not None and decode_error is None:
                try:
                    bridge_response = BridgeLiveResponse.model_validate(decoded)
                except ValueError:
                    bridge_response = None
                if bridge_response is not None:
                    structured_result = dict(bridge_response.result)
                    structured_result["bridge_returncode"] = completed.returncode
                    stderr = completed.stderr.strip()
                    if stderr:
                        structured_result["stderr"] = stderr
                    return BridgeExecutionResult(
                        domain=domain,
                        operation=operation,
                        success=False,
                        message=bridge_response.message,
                        error_code=(
                            bridge_response.error_code
                            if not bridge_response.success
                            else "bridge_nonzero_exit"
                        ),
                        execution_id=bridge_response.execution_id,
                        bridge_mode="live",
                        provider=bridge_response.provider or provider,
                        result=structured_result,
                    )
            details = (completed.stderr or completed.stdout or "").strip()
            if not details:
                details = "Bridge command failed"
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=details,
                error_code="bridge_nonzero_exit",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )

        decoded, decode_error = _decode_live_bridge_response(completed.stdout)
        if decode_error is not None or decoded is None:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=decode_error or "Live bridge returned an invalid response payload.",
                error_code="invalid_response",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )

        try:
            bridge_response = BridgeLiveResponse.model_validate(decoded)
        except ValueError as exc:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message=f"Live bridge response schema validation failed: {exc}",
                error_code="invalid_response",
                execution_id=None,
                bridge_mode="live",
                provider=provider,
                result={},
            )

        success_field = bridge_response.success
        execution_id = bridge_response.execution_id
        resolved_provider = bridge_response.provider or provider
        result = bridge_response.result

        if success_field:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=True,
                message=bridge_response.message,
                error_code=None,
                execution_id=execution_id,
                bridge_mode="live",
                provider=resolved_provider,
                result=result,
            )

        return BridgeExecutionResult(
            domain=domain,
            operation=operation,
            success=False,
            message=bridge_response.message,
            error_code=bridge_response.error_code or "execution_failed",
            execution_id=execution_id,
            bridge_mode="live",
            provider=resolved_provider,
            result=result,
        )

    @staticmethod
    def _execute_mock(
        *,
        domain: str,
        operation: str,
        payload: dict[str, object],
        rollback_class: RollbackClass | None,
        provider: str,
    ) -> BridgeExecutionResult:
        if operation.startswith("fail") or payload.get("force_fail") is True:
            return BridgeExecutionResult(
                domain=domain,
                operation=operation,
                success=False,
                message="Deterministic mock failure triggered by operation/payload.",
                error_code="mock_forced_failure",
                execution_id=_stable_execution_id(domain, operation, payload),
                bridge_mode="mock",
                provider=provider,
                result={},
            )

        return BridgeExecutionResult(
            domain=domain,
            operation=operation,
            success=True,
            message=f"Mock bridge executed {domain}.{operation}",
            error_code=None,
            execution_id=_stable_execution_id(domain, operation, payload),
            bridge_mode="mock",
            provider=provider,
            result=_normalize_result_payload(
                mock_result(domain, operation, payload, rollback_class)
            ),
        )


def _stable_execution_id(domain: str, operation: str, payload: dict[str, object]) -> str:
    stable_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{domain}:{operation}:{stable_payload}".encode()).hexdigest()
    return f"mock-{digest[:16]}"


def _normalize_execution_id(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _normalize_result_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _live_bridge_timeout_seconds_from_environment() -> float:
    raw_timeout = os.getenv(LIVE_BRIDGE_TIMEOUT_ENV)
    if raw_timeout is None:
        return DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS

    try:
        timeout_seconds = float(raw_timeout.strip())
    except ValueError:
        return DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS

    if timeout_seconds <= 0:
        return DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS

    return timeout_seconds


def _decode_live_bridge_response(output: str) -> tuple[dict[str, object] | None, str | None]:
    payload = output.strip()
    if not payload:
        return None, "Live bridge returned empty output."

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None, "Live bridge returned non-JSON output."

    if not isinstance(decoded, dict):
        return None, "Live bridge returned non-object JSON output."

    return {str(key): value for key, value in decoded.items()}, None


DEFAULT_BRIDGE = FLStudioBridge.from_environment()


def execute_operation(
    *,
    domain: str,
    operation: str,
    payload: dict[str, object],
    rollback_class: RollbackClass,
    provider: str | None = None,
) -> BridgeExecutionResult:
    """Compatibility helper for direct bridge execution from typed values."""

    change = DomainChange(
        domain=domain,
        operation=operation,
        rollback_class=rollback_class,
        provider=provider,
        payload=payload,
    )
    result = DEFAULT_BRIDGE.execute_change(change)
    logger.info(
        "Bridge execute: domain=%s operation=%s success=%s mode=%s",
        domain,
        operation,
        result.success,
        result.bridge_mode,
    )
    return result


def _resolve_provider(
    mode: BridgeMode,
    domain: str,
    operation: str,
    payload: dict[str, object],
    provider_hint: str | None,
) -> str:
    requested = provider_hint or payload.get("provider")
    if isinstance(requested, str) and requested and requested != "auto":
        return _PROVIDER_ALIASES.get(requested, requested)
    if mode == "mock":
        return "mock"
    if forced_live_flapi_supports(domain, operation):
        return "flapi-live"
    return default_provider_for_operation(domain, operation)


def _mock_supports_operation(domain: str, operation: str) -> bool:
    return (
        operation == "noop" or operation.startswith("fail") or (domain, operation) in _MOCK_DISPATCH
    )


def _supported_operations(domain: str) -> list[str]:
    return sorted(op for (d, op) in _MOCK_DISPATCH if d == domain)
