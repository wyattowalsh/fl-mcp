"""Generate JSON Schema artifacts from canonical Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from fl_mcp.schemas import (
    PluginCalibration,
    PluginControl,
    PluginInventoryItem,
    PluginPresetAsset,
    PluginProfile,
    PluginRawParameter,
    PluginSupportMatrixRow,
    PluginValueMap,
    PluginWrapperFingerprint,
    ProviderManifest,
    Snapshot,
    TransactionEnvelope,
    TransactionResult,
)


class JsonSchemaModel(Protocol):
    @classmethod
    def model_json_schema(cls) -> dict[str, object]: ...


MODEL_REGISTRY = {
    "plugin-calibration": PluginCalibration,
    "plugin-control": PluginControl,
    "plugin-inventory-item": PluginInventoryItem,
    "plugin-preset-asset": PluginPresetAsset,
    "plugin-profile": PluginProfile,
    "plugin-raw-parameter": PluginRawParameter,
    "plugin-support-matrix-row": PluginSupportMatrixRow,
    "plugin-value-map": PluginValueMap,
    "plugin-wrapper-fingerprint": PluginWrapperFingerprint,
    "provider-manifest": ProviderManifest,
    "snapshot": Snapshot,
    "transaction-envelope": TransactionEnvelope,
    "transaction-result": TransactionResult,
}  # type: dict[str, type[JsonSchemaModel]]


def generate_schemas(output_dir: Path) -> None:
    """Generate deterministic JSON schemas for public contracts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, model in MODEL_REGISTRY.items():
        (output_dir / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    generate_schemas(root / "docs" / "generated" / "schemas")


if __name__ == "__main__":
    main()
