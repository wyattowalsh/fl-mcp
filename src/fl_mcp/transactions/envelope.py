"""Transaction envelope validation and rollback classification."""

from __future__ import annotations

from typing import Any

REQUIRED_KEYS = {"request_id", "mode", "changes"}
ROLLBACK_CLASSIFICATIONS = {
    "validation_error": "input_error",
    "provider_error": "external_failure",
    "timeout": "retryable_timeout",
}


def validate_envelope(envelope: dict[str, Any]) -> bool:
    """Validate basic transaction envelope shape."""
    missing = REQUIRED_KEYS.difference(envelope.keys())
    if missing:
        return False
    return isinstance(envelope.get("changes"), list)


def rollback_classification_presence() -> set[str]:
    """Return known rollback classification keys."""
    return set(ROLLBACK_CLASSIFICATIONS.keys())
