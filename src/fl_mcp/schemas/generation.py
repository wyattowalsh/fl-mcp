"""Schema generation helpers."""

from __future__ import annotations

import json

from fl_mcp.schemas.transaction import TransactionEnvelope


def generate_schema_json() -> str:
    """Serialize canonical transaction envelope schema deterministically."""
    schema = TransactionEnvelope.model_json_schema()
    return json.dumps(schema, sort_keys=True, indent=2)
