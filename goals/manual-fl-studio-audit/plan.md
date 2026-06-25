# Manual FL Studio Audit Plan

## Solution Approach

Treat the accepted facts in `facts.md` as an audit contract. The goal is to prove, against the current local checkout and real local FL Studio app, whether fl-mcp can support agent-driven production flows through MCP. The output is not a patch set. The output is a complete evidence-backed audit report, severity-led issue ledger, and ordered refinement/fixer plan.

The audit must be exhaustive about the current user-facing surface: 12 compact tools, 5 resources, 3 resource templates, 8 prompts, CLI/helper/docs flows, bridge setup options, and all 216 internal FL Studio operations. Current local evidence must be refreshed at run time, so the audit must attempt all cataloged operations live where technically callable and classify unsupported results honestly.

Current-doc sources to refresh at run time:

- FastMCP docs index: `https://gofastmcp.com/llms.txt`
- FastMCP background tasks: `https://gofastmcp.com/servers/tasks.md`
- FastMCP tool search transforms: `https://gofastmcp.com/servers/transforms/tool-search.md`
- FastMCP testing: `https://gofastmcp.com/servers/testing.md`
- FastMCP tool fingerprinting: `https://gofastmcp.com/servers/tool-fingerprinting.md`
- MCP docs index: `https://modelcontextprotocol.io/llms.txt`
- MCP latest spec index: `https://modelcontextprotocol.io/specification/2025-11-25/index.md`
- MCP tasks extension/spec material: `https://modelcontextprotocol.io/extensions/tasks/overview.md` and `https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks.md`
- MCP security best practices: `https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices.md`
- Image-Line MIDI scripting docs: `https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm`

## Ordered Steps

1. Re-ground the repository and create an audit workspace.
   - Touches: `goals/manual-fl-studio-audit/`, `BUILD_STATUS.md` if it remains required by repo instructions and is still missing.
   - Work:
     - Re-read `AGENTS.md`, `src/AGENTS.md`, `fl-bundle/AGENTS.md`, and `helper/AGENTS.md`.
     - Re-check branch and dirty state with `git status --short --branch`; do not reset, stash, commit, push, or clean unrelated work.
     - Create a timestamped audit workspace such as `goals/manual-fl-studio-audit/run-YYYYMMDD-HHMMSS/`.
     - Start `audit-log.md`, `operation-matrix.jsonl`, `issue-ledger.md`, and `fixer-plan.md`.
     - If `BUILD_STATUS.md` is still absent, record that repo-instruction conflict and decide whether the audit ledger should restore it as a non-code audit artifact.
   - Verification:
     - `git status --short --branch`
     - `find goals/manual-fl-studio-audit -maxdepth 2 -type f | sort`

2. Refresh protocol and dependency context.
   - Touches: audit notes only unless docs drift is later logged as a finding.
   - Work:
     - Re-fetch the current official docs listed above. Use `llms.txt` before broader web search.
     - Verify the local dependency state and latest FastMCP version. Current preflight found `fastmcp` `3.4.2` on PyPI and local inspect reported FastMCP `3.4.2` with MCP `1.26.0`.
     - Record current MCP spec version; current official docs present `2025-11-25` as the latest visible spec.
     - Capture FastMCP requirements relevant to this audit: `fastmcp[tasks]`, async-only task handlers for `task=True`, FastMCP client testing, tool search transforms for large catalogs, and fingerprinting for schema drift.
     - Capture MCP security requirements relevant to a local server: stdio preference, explicit local command consent, least-privilege/scope minimization, no token passthrough, guarded local HTTP exposure.
   - Verification:
     - `curl -fsSL https://gofastmcp.com/llms.txt | sed -n '1,80p'`
     - `curl -fsSL https://modelcontextprotocol.io/llms.txt | sed -n '1,120p'`
     - `curl -fsSL https://pypi.org/pypi/fastmcp/json | jq -r '.info.version'`
     - `COLUMNS=1000 uv run fastmcp inspect fastmcp.json --format mcp > /tmp/fl-mcp-inspect.json 2>/tmp/fl-mcp-inspect.err`
     - `jq '{tools: (.tools | length), resources: (.resources | length), prompts: (.prompts | length)}' /tmp/fl-mcp-inspect.json`

3. Generate the audit matrix from the current code, not README claims.
   - Touches: `goals/manual-fl-studio-audit/run-*/operation-matrix.jsonl`.
   - Reads: `src/fl_mcp/tools/compact.py`, `src/fl_mcp/tools/fl_surface.py`, `src/fl_mcp/schemas/compact_surface.py`, `src/fl_mcp/resources/surface.py`, `src/fl_mcp/prompts/registry.py`, `src/fl_mcp/providers/builtin.py`, `src/fl_mcp/bridge/live_surface.py`, `docs/content/docs/architecture/public-api-inventory.mdx`.
   - Work:
     - Export compact tool names, resource URIs, template URIs, prompt names, provider matrix, operation IDs, schema model names, example requests, safety annotations, rollback classes, task flags, execution modes, and default providers.
     - Record current counts. Release-candidate preflight found 12 compact tools, 216 operations across 16 domains, 5 resources, 3 templates, 8 prompts, and 4 providers.
     - Record safety buckets from the current catalog instead of relying on earlier preflight counts.
     - Record provider-default buckets from the current catalog instead of relying on earlier preflight counts.
     - Mark every row with planned live attempt mode: read, reversible write, temp-file write, destructive scratch-only, unsupported-classification expected, or manual checkpoint required.
   - Verification:
     - `uv run python - <<'PY'` with imports from `fl_mcp.tools.fl_surface`, `fl_mcp.tools.compact`, `fl_mcp.bridge.live_surface`, and `fl_mcp.prompts.registry` to print the current counts.
     - `uv run pytest tests/contract/test_public_surface.py tests/unit/test_fl_surface_comprehensive.py tests/unit/test_mock_dispatch_coverage.py tests/unit/test_provider_runtime.py`

4. Preflight local CLI, docs, helper, and harness behavior.
   - Touches: audit notes only.
   - Reads: `src/fl_mcp/cli/main.py`, `src/fl_mcp/cli/install.py`, `src/fl_mcp/cli/doctor.py`, `src/fl_mcp/cli/config.py`, `src/fl_mcp/cli/diagnostics.py`, `src/fl_mcp/cli/server.py`, `helper/Sources/FLMCPHelper/HelperViewModel.swift`, `helper/Sources/FLMCPHelper/ContentView.swift`, `docs/content/docs/installation.mdx`, `docs/content/docs/getting-started.mdx`, `docs/content/docs/clients/**`.
   - Work:
     - Exercise every CLI option and output shape: version, server dry-runs, install local/system dry-run, doctor table/json, config env/json, diagnostics status/diagnostics.
     - Verify docs command snippets against the current checkout, including local editable `uvx --from ... --with-editable ...` examples where practical.
     - Run helper tests and manually inspect helper behavior: Check Status, Run Diagnostics, disabled running state, error rendering, log list, and repository-root command inference.
     - Capture the gap that `doctor` proves harness health, not actual FL Studio app polling.
   - Verification:
     - `uv run fl-mcp --version`
     - `uv run fl-mcp server run --mode stdio --dry-run`
     - `uv run fl-mcp server run --mode http --dry-run --host 127.0.0.1 --port 8765 --path /mcp`
     - `uv run fl-mcp install --target local --dry-run`
     - `uv run fl-mcp install --target system --dry-run`
     - `uv run fl-mcp doctor --format table`
     - `uv run fl-mcp doctor --format json`
     - `uv run fl-mcp config shell --format env`
     - `uv run fl-mcp config shell --format json`
     - `uv run fl-mcp diagnostics shell --endpoint status`
     - `uv run fl-mcp diagnostics shell --endpoint diagnostics`
     - `(cd helper && swift test)`
     - `pnpm --dir docs --ignore-workspace docs:verify-reference`
     - `pnpm --dir docs --ignore-workspace check`
     - `pnpm --dir docs --ignore-workspace build`

5. Establish the scratch FL Studio live environment.
   - Touches: FL Studio scratch project and temporary files only; audit notes.
   - Reads: `src/fl_mcp/bridge/bundle.py`, `src/fl_mcp/bridge/host_client.py`, `fl-bundle/controller/device_FL_MCP_Bridge.py`, `docs/content/docs/architecture/bridge-protocol.mdx`.
   - Work:
     - Use `uv run fl-mcp install --dry-run` to capture the current `FL_MCP_BRIDGE_MODE`, `FL_MCP_FL_STUDIO_BRIDGE_CMD`, `FL_MCP_FL_STUDIO_BRIDGE_DIR`, controller source, controller target, uvx env blocks, harness env blocks, and selected-controller env blocks.
     - Verify the controller script exists at `fl-bundle/controller/device_FL_MCP_Bridge.py`.
     - Copy the controller script to the reported target only after checking the target path, then verify byte match with `cmp -s`.
     - Ensure the bridge directory exists, is not a symlink, is owned by the current user, and has `0700` permissions.
     - Launch FL Studio locally, select `FL MCP Bridge` in MIDI Settings, open a dedicated scratch project, and make no personal FLP file the active test target.
     - Verify actual script initialization through `fl_mcp_bridge.log`, `status.json`, request/response file movement, or a successful MCP read.
     - If UI automation is available, use it for FL Studio launch/controller-selection evidence. Otherwise, use user checkpoints for those UI-only steps and keep MCP execution as the production path under audit.
   - Verification:
     - `uv run fl-mcp install --dry-run`
     - `test -f fl-bundle/controller/device_FL_MCP_Bridge.py`
     - `cmp -s fl-bundle/controller/device_FL_MCP_Bridge.py "/Users/ww/Documents/Image-Line/FL Studio/Settings/Hardware/FL MCP Bridge/device_FL_MCP_Bridge.py"`
     - `BRIDGE_DIR="$(uv run fl-mcp install --dry-run | jq -r '.environment.FL_MCP_FL_STUDIO_BRIDGE_DIR')"; ls -ld "$BRIDGE_DIR"`
     - `BRIDGE_DIR="$(uv run fl-mcp install --dry-run | jq -r '.environment.FL_MCP_FL_STUDIO_BRIDGE_DIR')"; find "$BRIDGE_DIR" -maxdepth 1 -type f -print`
     - `FL_MCP_BRIDGE_MODE=live FL_MCP_FL_STUDIO_BRIDGE_CMD="$(uv run python -c 'from fl_mcp.bridge.bundle import file_bridge_command; print(file_bridge_command())')" FL_MCP_FL_STUDIO_BRIDGE_DIR="$(uv run fl-mcp install --dry-run | jq -r '.environment.FL_MCP_FL_STUDIO_BRIDGE_DIR')" uv run python -c 'from fl_mcp.tools.compact import fl_execute; print(fl_execute("transport.get_state", {}, provider="flapi-live"))'`

6. Audit the compact MCP surface in mock, harness, and live modes.
   - Touches: audit artifacts only.
   - Reads: `src/fl_mcp/server/factory.py`, `src/fl_mcp/tools/compact.py`, `src/fl_mcp/schemas/compact_surface.py`, `tests/contract/test_public_surface.py`, `tests/unit/test_server_creation.py`.
   - Work:
     - Use a FastMCP client test harness to list tools, resources, resource templates, and prompts.
     - Call `fl_status` and verify `internal_operation_count=216`, provider statuses, bridge state, and task counts.
     - Call `fl_snapshot` for `project`, `arrangement`, `capabilities`, and representative domain values.
     - Exercise `fl_search_capabilities` options: `query`, `domain`, `provider`, `read_only`, `destructive`, `task`, and `limit`, including limit bounds.
     - Exercise `fl_get_capability_schema` for every operation ID and verify request/response schema presence, example request validity, provider support, and safety guidance.
     - Exercise `fl_browser` actions `search`, `schema`, and `load` for every `BrowserKind` where the current schema permits it.
     - Exercise `fl_plan` and `fl_apply` with transaction envelopes for scratch-safe changes.
     - Exercise `fl_render` and `fl_analyze_audio` as FastMCP native task-capable tools and verify task/resource alignment for `render://jobs/{job_id}` and `audio://analyses/{analysis_id}`.
   - Verification:
     - `COLUMNS=1000 uv run fastmcp inspect fastmcp.json --format mcp > /tmp/fl-mcp-inspect.json 2>/tmp/fl-mcp-inspect.err`
     - `jq '.tools | length' /tmp/fl-mcp-inspect.json`
     - `uv run pytest tests/contract/test_public_surface.py tests/unit/test_server_creation.py tests/unit/test_fl_surface_task_tools.py tests/integration/test_request_lifecycle.py`
     - A new or temporary audit script that fails if any operation lacks schema, example, provider support, or classification.

7. Attempt every cataloged operation through the live MCP path.
   - Touches: `operation-matrix.jsonl`, `live-evidence.md`, scratch FL Studio project, temporary media/project files.
   - Reads: `src/fl_mcp/tools/compact.py`, `src/fl_mcp/tools/fl_surface.py`, `src/fl_mcp/bridge/fl_studio.py`, `src/fl_mcp/bridge/live_surface.py`, `src/fl_mcp/bridge/host_client.py`, `src/fl_mcp/bridge/selected_controller_client.py`, `fl-bundle/controller/device_FL_MCP_Bridge.py`.
   - Work:
     - Generate a live attempt request for each operation using `example_request_for_spec`, then rewrite file paths, project paths, render paths, sample paths, and plugin names to scratch-safe local fixtures.
     - Run reads first, reversible writes second, temp-file writes third, and destructive scratch-only operations last.
     - For each operation, attempt the production path through `fl_execute` or `fl_batch_execute` with readback when available.
     - For each operation, record operation id, request, provider requested, provider resolved, default provider, bridge mode, execution id, status, result summary, error code, message, readback result, elapsed time, FL Studio state note, and evidence artifact paths.
     - For operations whose default provider is `mock`, explicitly test whether a live provider override is accepted, rejected, or falls back to mock. Classify the result rather than treating mock success as live success.
     - For selected-controller-compatible operations, run a separate selected-controller pass when the local FL Studio session has that controller available.
     - For destructive operations, require an active scratch-project checkpoint and record before/after state. If the operation cannot be isolated safely, classify it as safety-gated instead of running it against personal state.
   - Verification:
     - Every one of the 216 operation IDs appears exactly once in the final live matrix.
     - Every matrix row has one of the accepted classifications: live success, live unsupported, blocked by FL Studio/API/app state, validation bug, bridge bug, docs/UX gap, or safety-gated.
     - `uv run pytest tests/unit/test_bridge_execution.py tests/unit/test_bridge_host_client.py tests/unit/test_bridge_mode_transparency.py tests/unit/test_tool_dispatch.py`

8. Audit negative, degraded, and safety paths.
   - Touches: audit artifacts only; temporary bridge directories/files.
   - Reads: `src/fl_mcp/bridge/fl_studio.py`, `src/fl_mcp/bridge/host_client.py`, `src/fl_mcp/bridge/selected_controller_client.py`, `src/fl_mcp/auth/token.py`, `src/fl_mcp/schemas/**`, `docs/content/docs/architecture/bridge-protocol.mdx`, `docs/content/docs/troubleshooting.mdx`.
   - Work:
     - Verify missing live command, invalid live command, timeout, nonzero subprocess, empty stdout, non-JSON stdout, non-object JSON, invalid request JSON, malformed known-operation payload, unsupported operation, unknown operation id, provider mismatch, mock/live transparency, auth-token requirements, helper command failures, and docs troubleshooting coverage.
     - Verify host-file bridge security paths: symlink bridge dir, non-directory bridge path, wrong permissions, stale request/response files, and `keep_files` diagnostic behavior where applicable.
     - Verify selected-controller paths: missing directory, unsupported operation, lock/busy, timeout, malformed response, explicit selected-controller error, and successful mixer/transport compatible operations.
     - Verify local HTTP mode uses loopback defaults and auth warnings are visible; do not expose non-loopback HTTP without explicit approval.
   - Verification:
     - `uv run pytest tests/unit/test_error_paths.py tests/unit/test_auth_token_enforcement.py tests/unit/test_auth_edge_cases.py tests/unit/test_bridge_host_client.py tests/unit/test_bridge_mode_transparency.py tests/integration/test_cli_edge_cases.py`
     - Targeted shell probes using temporary directories under `mktemp -d`, with no personal files.

9. Analyze findings into a severity-led issue ledger.
   - Touches: `goals/manual-fl-studio-audit/run-*/issue-ledger.md`.
   - Work:
     - For every finding, record severity, title, affected user flow, affected files/systems, reproduction steps, exact command or MCP request, expected behavior, actual behavior, raw error/status, evidence artifact, likely root cause, user impact, and proposed verification.
     - Severity guidance:
       - P0: corrupts or risks personal FL Studio work, secrets, or uncontrolled local execution.
       - P1: blocks agent-driven production flow, live bridge use, or all-operation audit completeness.
       - P2: misleading provider metadata, incomplete diagnostics, docs mismatch, schema/options bug, or recoverable UX break.
       - P3: polish, wording, duplicate guidance, or low-risk helper/docs gaps.
     - Keep mock-only success, harness success, and actual FL Studio success separate.
     - Explicitly note where docs say live FL Studio is optional but this accepted goal requires local live validation.
   - Verification:
     - Every accepted fact maps to at least one audit section and at least one evidence source.
     - Every failed or blocked operation has a ledger entry or is grouped under a justified class-level issue.

10. Craft the refinement/fixer plan.
   - Touches: `goals/manual-fl-studio-audit/run-*/fixer-plan.md`.
   - Work:
     - Order remediation by severity and dependency: safety/secret/destructive guards first, bridge correctness and live connection evidence second, provider metadata/schema truthfulness third, missing live adapters fourth, CLI/helper/docs UX fifth, regression and docs automation last.
     - For each fix item, name files/systems likely touched, exact behavioral change, tests to add/update, manual FL Studio re-test, and docs/API inventory updates.
     - If a future fix would change public APIs, file structure, downstream agent tooling, docs generation, validation behavior, or release workflow, require OpenSpec before implementation.
     - If a future fix changes public APIs, file structure, agent definitions, or skill definitions, require `/docs-steward` if available.
     - Keep the fixer plan as a plan. Do not implement fixes, commit, push, publish, reset, or clean dirty work unless the active user explicitly redirects the goal.
   - Verification:
     - Every P0/P1 issue has a concrete fix lane and verification command.
     - Every live-only issue has a manual FL Studio re-test gate.
     - Every automated-verification fact has an automated command, script, or documented blocker.

11. Close the audit package.
   - Touches: `goals/manual-fl-studio-audit/run-*/audit-report.md`, `issue-ledger.md`, `fixer-plan.md`, `operation-matrix.jsonl`, and optionally `BUILD_STATUS.md` if repo instructions require the ledger to be current.
   - Work:
     - Summarize what was fully verified, what was live-attempted but unsupported, what was blocked, and what remains safety-gated.
     - Include exact local versions, FastMCP/MCP versions, FL Studio app/version evidence, command outputs, bridge paths, controller target path, test counts, and timestamps.
     - Re-run focused automated checks after producing the artifacts.
     - Inspect the final diff and keep edits scoped to the goal artifacts and any required status ledger.
   - Verification:
     - `jq -c . goals/manual-fl-studio-audit/run-*/operation-matrix.jsonl >/dev/null` or an equivalent JSONL validator.
     - `uv run pytest tests/contract/test_public_surface.py tests/unit/test_bridge_host_client.py tests/integration/test_cli.py`
     - `uv run pytest tests/unit/test_fl_surface_comprehensive.py tests/unit/test_mock_dispatch_coverage.py tests/unit/test_provider_runtime.py`
     - `(cd helper && swift test)`
     - `pnpm --dir docs --ignore-workspace docs:verify-reference`
     - `pnpm --dir docs --ignore-workspace check`
     - `pnpm --dir docs --ignore-workspace build`
     - `git diff -- goals/manual-fl-studio-audit BUILD_STATUS.md`

## Risks and Open Questions

- The current default live bridge is intentionally narrow. A complete audit will likely produce many live unsupported classifications unless additional live adapters already exist outside the visible repo paths.
- `fl-mcp doctor --format json` can be green through the harness while the real FL Studio controller script is not installed, selected, or polling.
- Exhaustively attempting 216 operations against a DAW can mutate project state. The audit must use scratch projects, temp files, and active checkpoints for destructive operations.
- Some operation examples currently use `mock://` paths or generic plugin names. The audit runner must rewrite those to real scratch fixtures or classify the operation as fixture-blocked.
- The helper currently surfaces `diagnostics shell` output, not full doctor/live bridge readiness. That may be a real UX gap for local users trying to diagnose FL Studio control.
- The current working tree is heavily dirty and includes deleted `BUILD_STATUS.md`, while repo instructions require maintaining it. The audit should not discard unrelated work, but it should record this mismatch.
- FastMCP and MCP task support are current as of this setup pass, but both are active projects. Re-check official docs and package versions during the actual audit run.
- Local FL Studio UI automation may be limited. If desktop automation cannot select controllers or handle dialogs reliably, use user checkpoints for those UI-only setup actions and keep all production behavior tests MCP-driven.
