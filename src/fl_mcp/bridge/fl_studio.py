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

    def __init__(self, *, mode: BridgeMode = "mock", live_command: str | None = None) -> None:
        self.mode = mode
        self.live_command = live_command

    @classmethod
    def from_environment(cls) -> FLStudioBridge:
        configured_mode = os.getenv("FL_MCP_BRIDGE_MODE", "mock").strip().lower()
        mode: BridgeMode = "live" if configured_mode == "live" else "mock"
        command = os.getenv("FL_MCP_FL_STUDIO_BRIDGE_CMD")
        return cls(mode=mode, live_command=command)

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

        try:
            decoded = json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError:
            decoded = {}

        if not isinstance(decoded, dict):
            decoded = {}

        success = bool(decoded.get("success", True))
        message = str(decoded.get("message", "Live bridge executed"))
        execution_id = decoded.get("execution_id")
        if execution_id is not None and not isinstance(execution_id, str):
            execution_id = None

        return BridgeExecutionResult(
            domain=change.domain,
            operation=change.operation,
            success=success,
            message=message,
            error_code=None if success else str(decoded.get("error_code") or "unknown"),
            execution_id=execution_id,
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
