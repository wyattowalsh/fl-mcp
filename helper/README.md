# FL MCP Helper

SwiftUI window for local FL MCP diagnostics. `Package.swift` builds the `FLMCPHelper` executable, and `FLMCPHelperApp` presents a `WindowGroup`.

## Window

- Status shows the latest doctor health value.
- The log lists doctor log lines, check summaries, and errors.
- Check Status calls `fetchStatus()`.
- Run Diagnostics calls `runDiagnostics()`.

Both actions run `uv run fl-mcp doctor --format json` and decode the JSON payload. A non-zero exit still displays that payload when stdout matches the status object. When it does not, the window shows a failed `doctor` check that includes the exit code.

## Contract

The JSON fields and exit behavior are documented in `docs/interfaces.md`. The payload model is `HelperStatusPayload` in `src/fl_mcp/interfaces/status.py`.
