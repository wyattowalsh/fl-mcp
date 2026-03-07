"""Generate JSON Schema artifacts from Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from fl_mcp.schemas import ProviderManifest, Snapshot, TransactionEnvelope, TransactionResult


def generate_schemas(output_dir: Path) -> None:
    """Generate deterministic JSON schemas for public contracts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "transaction-envelope": TransactionEnvelope,
        "transaction-result": TransactionResult,
        "snapshot": Snapshot,
        "provider-manifest": ProviderManifest,
    }
    for name, model in models.items():
        (output_dir / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    generate_schemas(root / "docs" / "generated" / "schemas")


if __name__ == "__main__":
    main()
