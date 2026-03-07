# fl-mcp

Scaffold for FL MCP CLI, bundle layout, and macOS helper app.

## Layout

- `src/fl_mcp/cli/`: CLI package and subcommands.
- `src/fl_mcp/interfaces/`: shared status/diagnostics contracts.
- `fl-bundle/`: bundle scaffold for controller, piano-roll, vfx, and shared assets.
- `helper/`: macOS Swift/SwiftUI shell project (`FL MCP Helper`).
- `docs/interfaces.md`: CLI ↔ helper endpoint contract.

## CLI commands (scaffold)

- `server run --mode stdio|http`
- `install`
- `doctor`
- `config shell`
- `diagnostics shell`
