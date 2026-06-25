"""Typed contracts for the FL Studio subprocess bridge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fl_mcp.schemas.transaction import RollbackClass


class BridgeLiveRequest(BaseModel):
    """JSON payload passed to a live bridge subprocess."""

    domain: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    rollback_class: RollbackClass | None = None
    provider: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Optional stable key for bridge retries. When set, host_client reuses "
            "the key as request_id and returns an existing response file when present."
        ),
    )


class BridgeLiveResponse(BaseModel):
    """JSON payload returned from a live bridge subprocess."""

    success: bool
    message: str
    error_code: str | None = None
    execution_id: str | None = None
    provider: str | None = None
    result: dict[str, object] = Field(default_factory=dict)


class BridgeRunnerModeResponse(BaseModel):
    """Runner mode descriptor used by CLI diagnostics."""

    command: str
    harness_command: str
    direct_command: str
    selected_controller_command: str
    uvx_command: str
    uvx_harness_command: str
    uvx_direct_command: str
    uvx_selected_controller_command: str
    bridge_dir: str
    selected_controller_dir: str
    controller_script: str
    hardware_script_dir: str
    status: Literal["available", "missing"]
    details: str
