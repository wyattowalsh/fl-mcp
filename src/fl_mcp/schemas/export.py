"""Generate deterministic JSON Schema artifacts from Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from .provider_manifests import ProviderManifest
from .results import MutationResult, TransactionResult
from .snapshots import GraphSnapshot
from .transactions import MutationModel, TransactionEnvelope

MODEL_REGISTRY: dict[str, Type[BaseModel]] = {
    "mutation_model": MutationModel,
    "transaction_envelope": TransactionEnvelope,
    "mutation_result": MutationResult,
    "transaction_result": TransactionResult,
    "graph_snapshot": GraphSnapshot,
    "provider_manifest": ProviderManifest,
}


def _stable_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def export_json_schemas(output_dir: Path | str = Path("docs/generated/schemas")) -> list[Path]:
    """Export schemas for all registered models to a deterministic output directory."""

    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for name in sorted(MODEL_REGISTRY):
        model = MODEL_REGISTRY[name]
        output_path = resolved_output_dir / f"{name}.schema.json"
        output_path.write_text(_stable_json(model.model_json_schema()), encoding="utf-8")
        written.append(output_path)

    return written


if __name__ == "__main__":
    export_json_schemas()
