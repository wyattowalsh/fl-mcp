# Close outstanding fl-mcp work

Make the November 16, 2026 audit findings true in the tree, and prove each code fix with a test.

Done means:

- The MIDI script resolves modules only from the FL module table, rejects unknown domains, and fails closed on the default bridge directory except for the documented embedded-Python `SystemError` case.
- The six mismatched operations (`channels.list_channels`, `patterns.list_patterns`, `patterns.select_pattern`, `patterns.create_pattern`, `patterns.rename_pattern`, `plugins.list_plugins`) can pass the non-mock provider capability check.
- `safety_mode="strict"` blocks delete, replace, open-project, and undo operations that the catalog describes as destructive.
- Apply no longer says a change was reverted when the server did not revert it.
- `host_client`, install, and doctor use the same default bridge directory as the installed controller script.
- `fl-mcp diagnostics shell` is not the helper's only health source; the helper can show doctor output.
- `just verify` exists and matches the Tier B runbook, HTTP docs match `server.py`, and live setup-check does not report safe when the controller is missing.
- `ruff check src tests` passes on the locked Ruff.
- Dependency-audit findings are bumped or recorded with the exact remaining advisory.
- HUMAN-T-310, HUMAN-T-312, and HUMAN-T-911 stay unchecked. Do not tag `v0.1.0`.
