# CLI ↔ Helper Interface Contract

This document defines a first-pass contract between FL MCP CLI diagnostics commands and the macOS helper UI.

## Endpoints

- `POST /v1/helper/status`
  - Used by helper to fetch current runtime status summary.
- `POST /v1/helper/diagnostics`
  - Used by helper to request detailed diagnostics output.

The endpoint constants are also defined in `src/fl_mcp/interfaces/status.py` as:

- `HELPER_STATUS_ENDPOINT`
- `HELPER_DIAGNOSTICS_ENDPOINT`

## Payload shape

All status payloads must conform to this JSON structure:

```json
{
  "service": "fl-mcp",
  "health": "ok | warning | error",
  "timestamp": "ISO-8601 UTC",
  "checks": [
    {
      "name": "check-name",
      "state": "ok | warning | error",
      "details": "human-readable details"
    }
  ],
  "logs": ["string lines"],
  "endpoint": "/v1/helper/status"
}
```

## CLI commands mapped to helper actions

- `fl-mcp diagnostics shell --endpoint status`
  - Emits payload for helper status panel.
- `fl-mcp diagnostics shell --endpoint diagnostics`
  - Emits payload for helper diagnostics panel.
- `fl-mcp doctor --format json`
  - Emits richer diagnostics payload that can be surfaced in logs.

## Helper action stubs

In `helper/Sources/FLMCPHelper/HelperViewModel.swift`, placeholders are provided for:

- `runInstallPlaceholder()`
- `runDiagnosticsPlaceholder()`

These methods should eventually execute CLI subprocess calls and decode this payload format.
