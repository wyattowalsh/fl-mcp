"""Transaction envelope validation and rollback classification."""

from __future__ import annotations

from pydantic import ValidationError

from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.transactions.rollback import ROLLBACK_POLICY_BY_CLASSIFICATION


def validate_envelope(envelope: dict[str, object]) -> bool:
    """Validate envelope using canonical schema contracts."""
    try:
        TransactionEnvelope.model_validate(envelope)
    except ValidationError:
        return False
    return True


def rollback_classification_presence() -> set[str]:
    """Return known rollback classes from canonical rollback policy mapping."""
    return set(ROLLBACK_POLICY_BY_CLASSIFICATION.keys())
