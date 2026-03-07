# fl-mcp

## Schema generation

Pydantic v2 models are defined under `src/fl_mcp/schemas/` and can be exported to JSON Schema files with:

```bash
PYTHONPATH=src python -m fl_mcp.schemas.export
```

Generated artifacts are written deterministically (sorted model registry and sorted JSON keys) to:

- `docs/generated/schemas/`
