"""FL Studio bridge adapters with live subprocess + deterministic mock fallback."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Literal

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.schemas import DomainChange, RollbackClass

BridgeMode = Literal["mock", "live"]
DEFAULT_LIVE_BRIDGE_TIMEOUT_SECONDS = 5.0
LIVE_BRIDGE_TIMEOUT_ENV = "FL_MCP_FL_STUDIO_BRIDGE_TIMEOUT_SECONDS"


@dataclass(slots=True, frozen=True)
class BridgeExecutionResult:
    domain: str
    operation: str
    success: bool
    message: str
    error_code: str | None
    execution_id: str | None
    bridge_mode: BridgeMode


class FLStudioBridge:
    """Executes domain operations against a live bridge command or deterministic mock."""

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

    @classmethod
    def from_environment(cls) -> FLStudioBridge:
        configured_mode = os.getenv("FL_MCP_BRIDGE_MODE", "mock").strip().lower()
        mode: BridgeMode = "live" if configured_mode == "live" else "mock"
        command = os.getenv("FL_MCP_FL_STUDIO_BRIDGE_CMD")
        return cls(
            mode=mode,
            live_command=command,
            live_timeout_seconds=_live_bridge_timeout_seconds_from_environment(),
        )

    def execute_change(self, change: DomainChange) -> BridgeExecutionResult:
        if change.domain not in DOMAINS:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=f"Domain '{change.domain}' is not registered.",
                error_code="unsupported_domain",
                execution_id=None,
                bridge_mode=self.mode,
            )

        if self.mode == "live":
            return self._execute_live(change)

        return self._execute_mock(change)

    def _execute_live(self, change: DomainChange) -> BridgeExecutionResult:
        if not self.live_command:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message="Live bridge mode configured without FL_MCP_FL_STUDIO_BRIDGE_CMD.",
                error_code="bridge_process_error",
                execution_id=None,
                bridge_mode="live",
            )

        payload = {
            "domain": change.domain,
            "operation": change.operation,
            "rollback_class": change.rollback_class,
            "payload": change.payload,
        }

        try:
            completed = subprocess.run(
                [*shlex.split(self.live_command), json.dumps(payload, sort_keys=True)],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.live_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=(
                    "Live bridge command timed out after "
                    f"{self.live_timeout_seconds:g} seconds."
                ),
                error_code="bridge_timeout",
                execution_id=None,
                bridge_mode="live",
            )
        except OSError as exc:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=str(exc),
                error_code="bridge_process_error",
                execution_id=None,
                bridge_mode="live",
            )

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            if not details:
                details = "Bridge command failed"
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=details,
                error_code="bridge_nonzero_exit",
                execution_id=None,
                bridge_mode="live",
            )

        decoded, decode_error = _decode_live_bridge_response(completed.stdout)
        if decode_error is not None or decoded is None:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=decode_error or "Live bridge returned an invalid response payload.",
                error_code="invalid_response",
                execution_id=None,
                bridge_mode="live",
            )

        success_field = decoded.get("success")
        execution_id = _normalize_execution_id(decoded.get("execution_id"))

        if success_field is True:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=True,
                message=str(decoded.get("message", "Live bridge executed")),
                error_code=None,
                execution_id=execution_id,
                bridge_mode="live",
            )

        if success_field is False:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message=str(decoded.get("message", "Live bridge execution failed.")),
                error_code=str(decoded.get("error_code") or "execution_failed"),
                execution_id=execution_id,
                bridge_mode="live",
            )

        return BridgeExecutionResult(
            domain=change.domain,
            operation=change.operation,
            success=False,
            message="Live bridge response must include explicit success=true.",
            error_code="invalid_response",
            execution_id=None,
            bridge_mode="live",
        )

    @staticmethod
    def _execute_mock(change: DomainChange) -> BridgeExecutionResult:
        if change.operation.startswith("fail") or change.payload.get("force_fail") is True:
            return BridgeExecutionResult(
                domain=change.domain,
                operation=change.operation,
                success=False,
                message="Deterministic mock failure triggered by operation/payload.",
                error_code="mock_forced_failure",
                execution_id=_stable_execution_id(change.domain, change.operation, change.payload),
                bridge_mode="mock",
            )

        return BridgeExecutionResult(
            domain=change.domain,
            operation=change.operation,
            success=True,
            message=f"Mock bridge applied {change.domain}.{change.operation}",
            error_code=None,
            execution_id=_stable_execution_id(change.domain, change.operation, change.payload),
            bridge_mode="mock",
        )


def _stable_execution_id(domain: str, operation: str, payload: dict[str, object]) -> str:
    stable_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{domain}:{operation}:{stable_payload}".encode()).hexdigest()
    return f"mock-{digest[:16]}"


def _normalize_execution_id(value: object) -> str | None:
    return value if isinstance(value, str) else None


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
) -> BridgeExecutionResult:
    """Compatibility helper for direct bridge execution from typed values."""

    change = DomainChange(
        domain=domain,
        operation=operation,
        rollback_class=rollback_class,
        payload=payload,
    )
    return DEFAULT_BRIDGE.execute_change(change)
