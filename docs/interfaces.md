# CLI ↔ Helper Interface Contract

The SwiftPM helper status and diagnostics actions read one CLI command. They do not call HTTP routes.

## Command

`fetchStatus()` and `runDiagnostics()` in `helper/Sources/FLMCPHelper/HelperViewModel.swift` both run:

```bash
uv run fl-mcp doctor --format json
```

`fl-mcp doctor` prints a `HelperStatusPayload` JSON object. The model is `src/fl_mcp/interfaces/status.py`. The command handler is `src/fl_mcp/cli/doctor.py`.

Exit codes for that command:

- `0` when aggregated health is `ok` or `warning`
- `1` when aggregated health is `error`
- `1` when `--fail-on-warning` is set and health is `warning` (the helper does not pass that flag)

The process still prints the JSON object on those non-zero exits. The helper decodes stdout whenever it matches the payload below, including when the exit code is non-zero.

If the exit code is non-zero and stdout is not that object, the helper records health `error` and one failed `doctor` check. The check details include the exit code and any stderr text.

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

`endpoint` is a label on the payload. `HelperStatusPayload` defaults it to `/v1/helper/status`. The helper does not POST to that path, and there is no helper HTTP server. There are no `runInstallPlaceholder` or `runDiagnosticsPlaceholder` methods.

## Helper actions

The window in `helper/Sources/FLMCPHelper/ContentView.swift` calls:

- Check Status → `fetchStatus()`
- Run Diagnostics → `runDiagnostics()`

Both actions use the doctor command above.
