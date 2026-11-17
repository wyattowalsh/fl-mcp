# Plan

1. Restrict `device_FL_MCP_Bridge.py` module lookup to the FL table and fail closed on the default directory, except `SystemError`.
2. Add `domain_operation` aliases to provider capabilities without renaming `spec.name`.
3. Mark delete, replace, open-project, and undo operations destructive and cover them in strict-mode tests.
4. Replace the false revert message and set automatic rollback support to false. Update tests that expected `failed_rolled_back`.
5. Point `host_client` default bridge directory at `default_file_bridge_dir()`.
6. Teach the SwiftPM helper to surface `fl-mcp doctor --format json`, including a non-zero exit payload.
7. Add `just verify`, correct HTTP and bridge-protocol docs, and make live setup-check fail when the controller script is absent.
8. Fix current Ruff findings. Re-run `pip-audit` and bump the seven named packages when the lockfile allows it.
9. Run the focused pytest modules and `ruff check src tests`.
