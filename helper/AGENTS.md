# AGENTS.md (helper scope)

Scope: helper/**

## Helper App Boundary

- Keep the helper thin and diagnostics-focused.
- Avoid moving MCP orchestration, operation dispatch, provider routing, or bridge policy into the helper.
- The helper may surface status, diagnostics, install hints, and logs from the Python CLI. It should not become a second control plane.
- Keep helper-facing contracts aligned with `docs/interfaces.md` and `src/fl_mcp/interfaces/status.py`.

## Validation

- When helper contracts change, update `docs/interfaces.md` and run the relevant Swift/helper checks if the toolchain is available.
