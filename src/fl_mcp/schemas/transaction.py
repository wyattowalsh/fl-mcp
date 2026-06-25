"""Canonical transaction envelope schemas."""

from typing import Literal

from pydantic import BaseModel, Field

RollbackClass = Literal["fully_transactional", "checkpointed", "best_effort", "unsafe_raw"]


class DomainChange(BaseModel):
    """Typed domain change payload entry."""

    domain: str
    operation: str
    rollback_class: RollbackClass
    provider: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class TransactionEnvelope(BaseModel):
    """Canonical transaction request envelope."""

    schema_version: str = "1.0"
    request_id: str
    mode: Literal["preview", "apply"]
    execution_policy: Literal["all-or-nothing", "allow-partial"] = "all-or-nothing"
    safety_mode: Literal["strict", "standard", "relaxed"] = Field(
        default="standard",
        description=(
            "Safety policy: 'standard' allows all changes, 'strict' blocks destructive "
            "changes, and 'relaxed' is rejected."
        ),
    )
    freshness_policy: Literal["strict", "allow-stale"] = Field(
        default="strict", description="Reserved — accepted but not yet enforced."
    )
    target_snapshot_id: str | None = None
    changes: list[DomainChange]
    preconditions: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class TransactionResult(BaseModel):
    """Canonical transaction execution result."""

    transaction_id: str
    status: Literal["planned", "applied", "failed", "partially_applied"]
    checkpoint_id: str | None = None
    snapshot_before: str | None = None
    snapshot_after: str | None = None
    per_domain_results: dict[str, str] = Field(default_factory=dict)
    diff_summary: dict[str, object] = Field(default_factory=dict)
    rollback_capability: str = "available"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
