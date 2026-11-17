# CLI ↔ Helper Interface Contract

The SwiftPM helper reads JSON from `fl-mcp doctor --format json`. There is no helper HTTP server.

## Command

```bash
uv run fl-mcp doctor --format json
```

Doctor exits 0 for `ok` and `warning`, and exits 1 for `error`. The helper decodes stdout in both cases when the body is a status payload.

## Payload shape

```json
{
  "service": "fl-mcp",
  "health": "ok | warning | error",
  "timestamp": "ISO-8601 UTC",
  "endpoint": "/v1/helper/status",
  "checks": [
    {
      "name": "check-name",
      "state": "ok | warning | error",
      "details": "human-readable details"
    }
  ],
  "logs": ["string lines"],
  "errors": ["string lines"]
}
```

`endpoint` is a payload label from `src/fl_mcp/interfaces/status.py`. It is not an HTTP route.

## Helper actions

`helper/Sources/FLMCPHelper/HelperViewModel.swift` runs the doctor command from `fetchStatus()` and `runDiagnostics()`.
