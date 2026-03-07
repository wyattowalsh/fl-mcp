"""Schema generation helpers."""

from __future__ import annotations

import json
from typing import Any


BASE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TransactionEnvelope",
    "type": "object",
    "required": ["transaction_id", "operations"],
    "properties": {
        "transaction_id": {"type": "string"},
        "operations": {
            "type": "array",
            "items": {"type": "object"},
        },
    },
}


def generate_schema_json() -> str:
    """Serialize schema with stable key ordering and formatting."""
    return json.dumps(BASE_SCHEMA, sort_keys=True, indent=2)
