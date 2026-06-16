# Facts

- The goal is to audit the current fl-mcp local user experience end to end against the real local FL Studio app, with MCP-driven agent production flows as the primary product behavior.
- The audit scope covers the compact MCP tools, MCP resources/templates/prompts, the 216-operation internal FL Studio capability catalog, CLI install/doctor/server/config flows, live bridge paths, selected-controller compatibility, the macOS helper diagnostics surface, docs-guided setup, and error/safety paths.
- Every visible user flow, option, schema field, provider route, environment variable path, diagnostic mode, and documented setup path must be exercised or explicitly classified with evidence.
- The audit must attempt all 216 cataloged FL Studio operations live through the MCP path where technically callable, then classify each operation as live success, live unsupported, blocked by FL Studio/API/app state, validation bug, bridge bug, docs/UX gap, or safety-gated.
- Manual FL Studio UI interaction is only a bootstrap and verification aid; the desired production workflow is for the agent to handle FL Studio work through fl-mcp.
- Live mutation and destructive-flow tests must use a scratch FL Studio project, temporary files, or copied fixtures, and must not modify personal projects or assets without explicit active approval during the audit run.
- The audit must include negative and degraded paths such as missing or unselected bridge scripts, invalid bridge directories, bridge timeout, selected-controller missing/busy/timeout, malformed payloads, unsupported operations, auth/config failures, provider mismatch, and mock/live transparency.
- The output must include a severity-led issue ledger with reproduction evidence, expected versus actual behavior, affected files or systems, likely root cause, user impact, proposed fix, and re-test requirements for each finding.
- The fixer plan must optimize for release readiness, agent usability, architecture quality, regression coverage, and manual FL Studio re-test gates rather than only quick local patching.
- Verification must combine manual FL Studio evidence with automated checks for catalog completeness, schema/options coverage, MCP contract behavior, CLI diagnostics, bridge harness behavior, provider/runtime state, docs consistency, and regression tests for accepted fixes.
- No implementation fix, commit, push, release, reset, stash, or dirty-worktree cleanup is part of this goal-package setup unless the active user explicitly requests it later.
