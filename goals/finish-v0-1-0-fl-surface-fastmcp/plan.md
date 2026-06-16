# Finish v0.1.0 FL Surface and FastMCP Alignment Plan

## Solution Approach

Treat the accepted facts in `facts.md` as the release definition for v0.1.0. This is no longer a mock-only surface polish goal: it requires a repo-owned live bridge path, complete evidence-backed FL Studio surface mapping, native async support for useful long-running operations, agent-friendly discovery for a large catalog, and publish-ready release gates.

Implementation should stay governed and contract-first. The public MCP surface remains resources-first for reads, Pydantic v2 remains the schema source of truth, and any new public tool/resource must be justified in the public API inventory, release notes, tests, and `BUILD_STATUS.md`.

Current-doc sources to refresh at implementation time:

- FastMCP docs index and full docs: `https://gofastmcp.com/llms.txt`, `https://gofastmcp.com/llms-full.txt`
- MCP docs and current spec: `https://modelcontextprotocol.io/llms.txt`, `https://modelcontextprotocol.io/llms-full.txt`
- MCP progressive discovery guidance: `https://modelcontextprotocol.io/docs/learn/tool-orchestration`
- MCP security guidance: `https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices`
- Image-Line / FL Studio API docs and any repo-local bridge or bundle assets found during the audit

## Ordered Steps

1. Open the governed change and refresh research inputs.
   - Touches: `BUILD_STATUS.md`, `goals/finish-v0-1-0-fl-surface-fastmcp/`, likely an OpenSpec change file if the repo or `/Users/ww/dev/projects/agents` exposes `uv run wagents openspec`.
   - Work:
     - Re-check `AGENTS.md`, branch, and focused dirty state before edits.
     - Triage the existing dirty tree into intentional source changes, generated/build/cache outputs, local runtime artifacts, and obsolete scaffold remnants. Clean generated or local-only debris, reconcile intentional source changes into the release plan, and avoid destructive reset/stash operations unless the exact target is intentionally approved.
     - Start an OpenSpec change because the accepted facts affect public APIs, file structure, downstream agent tooling, docs generation, validation behavior, and release scope.
     - Refresh official FastMCP, MCP, tool orchestration, security, tasks, and Image-Line API sources.
     - Record research decisions in an ADR or architecture doc before changing the public surface.
   - Verification:
     - `git status --short --branch`
     - `uv run wagents openspec ... --format json` if available; otherwise document unavailability in the plan/ledger.
     - Link every external mapping claim to an official source or a repo-local implementation artifact.

2. Build a surface audit and gap register.
   - Touches: `src/fl_mcp/tools/fl_surface.py`, `src/fl_mcp/schemas/fl_tools.py`, `src/fl_mcp/bridge/mock_generators.py`, `src/fl_mcp/providers/builtin.py`, `src/fl_mcp/resources/surface.py`, `docs/content/docs/architecture/public-api-inventory.mdx`, new or updated gap-register docs/tests.
   - Work:
     - Compare `FL_TOOL_SPECS`, `_MOCK_DISPATCH`, provider matrices, public docs, generated inventory, bridge protocol, `fl-bundle/**`, and official FL Studio API surfaces.
     - Classify each candidate operation as mapped, duplicate/alias, unsafe, unavailable outside FL Studio, live-only, mock-only, or intentionally unmapped.
     - Add mappable missing operations only when they have evidence and a schema/bridge route; omit speculative workflow tools unless they are backed by concrete primitives.
   - Verification:
     - `uv run pytest tests/unit/test_mock_dispatch_coverage.py tests/unit/test_fl_surface_comprehensive.py tests/unit/test_tool_dispatch.py`
     - A new audit test or script fails when public inventory, specs, mocks, provider capabilities, and gap register drift.

3. Implement the repo-owned live bridge path.
   - Touches: `fl-bundle/controller/**`, `src/fl_mcp/bridge/fl_studio.py`, `src/fl_mcp/cli/install.py`, `src/fl_mcp/cli/doctor.py`, `src/fl_mcp/config/settings.py`, `docs/content/docs/architecture/bridge-protocol.mdx`, helper docs/tests as needed.
   - Work:
     - Replace the controller placeholder with a bundled bridge runner or installable FL Studio controller script that accepts the existing JSON bridge request contract and returns the same typed result/error envelope as mock mode.
     - Keep FL Studio API imports deferred so normal CI can run without FL Studio installed.
     - Launch and use the available FL Studio app for live validation, manipulating a disposable project as needed to prove real read and mutation operations through the MCP server.
     - Add a live-harness mode that exercises the same subprocess protocol in CI, but treat it as repeatable contract coverage rather than a substitute for actual app evidence.
     - Update `fl-mcp install` and `fl-mcp doctor` so users can discover, install, and validate the bridge command instead of seeing `scaffold-ready`.
   - Verification:
     - `uv run pytest tests/unit/test_bridge_execution.py tests/unit/test_transaction_apply_execution.py tests/integration/test_cli.py tests/integration/test_cli_edge_cases.py`
     - A new live-harness test runs with `FL_MCP_BRIDGE_MODE=live` and a repo-owned bridge command.
     - Actual app live smoke: launch FL Studio, read one state surface, perform one safe mutation, verify the changed state through the MCP server, then clean up the disposable project.

4. Harden bridge contracts, targeting, and safety.
   - Touches: `src/fl_mcp/schemas/fl_tools.py`, `src/fl_mcp/schemas/transaction.py`, `src/fl_mcp/bridge/fl_studio.py`, `src/fl_mcp/transactions/**`, `src/fl_mcp/auth/token.py`, tests under `tests/unit/test_error_paths.py`, `tests/unit/test_auth_*`, and bridge docs.
   - Work:
     - Add explicit bridge request/response schema validation before and after the live subprocess boundary.
     - Preserve no-shell execution, timeout handling, deterministic error codes, and no secret logging.
     - Verify destructive tools have truthful descriptions and annotations, and fail closed when live host capability is missing.
   - Verification:
     - `uv run pytest tests/unit/test_error_paths.py tests/unit/test_auth_token_enforcement.py tests/unit/test_auth_edge_cases.py tests/unit/test_bridge_mode_transparency.py`
     - `uv run ty check src`

5. Make native FastMCP async tasks real.
   - Touches: `pyproject.toml`, `uv.lock`, `src/fl_mcp/server/factory.py`, `src/fl_mcp/tools/fl_surface.py`, `src/fl_mcp/tools/public.py`, `src/fl_mcp/runtime/state.py`, `src/fl_mcp/schemas/runtime_surface.py`, task tests.
   - Work:
     - Upgrade and lock FastMCP to the current stable release with task support. PyPI currently reports `fastmcp` `3.4.2`; re-check at implementation time and use the `fastmcp[tasks]` extra because docs say `task=True` or `TaskConfig` requires optional task dependencies.
     - Convert task-enabled public handlers to async functions and use native FastMCP task registration for render/export, audio analysis, and any additional long-running bridge operations.
     - Keep inline behavior graceful for clients that do not request task execution.
     - Align repo-owned `render://jobs/{job_id}` and `audio://analyses/{analysis_id}` resources with native task IDs, statuses, artifacts, cancellation, and terminal results.
   - Verification:
     - `uv run pytest tests/unit/test_fl_surface_task_tools.py tests/unit/test_runtime_state.py tests/unit/test_server_factory_auth_bootstrap.py tests/integration/test_request_lifecycle.py`
     - Add a FastMCP `Client` smoke test that calls a task-capable tool with `task=True`, polls or awaits the task, and verifies the corresponding resource/template state.
     - `uv run fastmcp inspect fastmcp.json --format mcp`

6. Add the agentic discovery pattern for the large tool catalog.
   - Touches: `src/fl_mcp/resources/surface.py`, `src/fl_mcp/tools/public.py`, `src/fl_mcp/server/factory.py`, `docs/content/docs/architecture/public-api-inventory.mdx`, `docs/content/docs/clients/**`, tests.
   - Work:
     - Use MCP progressive discovery guidance to choose the minimal public shape. The likely path is to keep `runtime://capabilities` and `runtime://capabilities/{domain}` as the primary discovery surface and add one governed search/discovery tool only if the audit proves resources alone are insufficient for agent selection.
     - If added, make the discovery tool compact and bounded: query, domain, tag, provider, safety, task-capable, read-only, limit, and stable ordering.
     - Consider FastMCP transforms, component visibility, or profiled views for clients that cannot handle all 200+ tools.
   - Verification:
     - `uv run pytest tests/contract/test_public_surface.py tests/unit/test_resource_surface.py tests/unit/test_public_tools_edge_cases.py`
     - A new test proves discovery results are deterministic, bounded, and include enough schema/annotation metadata for an agent to pick a tool safely.

7. Reconcile docs, inventories, ADRs, and generated references.
   - Touches: `README.md`, `docs/content/docs/architecture/**`, `docs/content/docs/reference/generated/**`, `docs/content/docs/release-notes.mdx`, `adr/**`, `docs/generated/schemas/**`, `BUILD_STATUS.md`.
   - Work:
     - Update public API inventory for any added, removed, or semantically changed tools/resources/templates.
     - Update bridge protocol docs to describe bundled live bridge install, harness, async task behavior, and failure modes.
     - Update client docs so agents are guided toward resources/search before raw tool guessing.
     - Invoke `/docs-steward` if available after public API, file structure, agent-facing, or skill-facing changes; document unavailability if it is not available.
   - Verification:
     - `pnpm --dir docs --ignore-workspace docs:generate-reference`
     - `pnpm --dir docs --ignore-workspace check`
     - `pnpm --dir docs --ignore-workspace build`

8. Make the release publish-ready.
   - Touches: `pyproject.toml`, `src/fl_mcp/__init__.py`, `fastmcp.json`, `.github/workflows/release-*.yml`, `README.md`, `docs/content/docs/release-notes.mdx`, `uv.lock`.
   - Work:
     - Move from `0.1.0a0` to `0.1.0` only after the live bridge, async tasks, surface audit, and docs are green.
     - Verify stable release workflows already cover tag/version matching, build artifacts, SHA256SUMS, provenance attestation, TestPyPI, PyPI, and GitHub release; patch only real gaps.
     - Confirm client install/config instructions work with the final bridge and FastMCP dependency set.
   - Verification:
     - `uv run python -m build` or `uv build`
     - `uv run --with twine==6.2.0 twine check dist/*`
     - `uv run fastmcp inspect fastmcp.json --format mcp`
     - Release workflow static checks and any local workflow lint available in the repo.

9. Run the complete validation matrix and close the ledger.
   - Touches: `BUILD_STATUS.md`, any generated artifacts from validation.
   - Work:
     - Run focused tests after each lane, then full repo validation once the implementation settles.
     - Leave the repository shipshape: remove generated/cache/runtime clutter from version control scope, reconcile source/docs/test changes into coherent release work, and inspect the final diff before claiming completion.
   - Verification:
     - `uv run ruff check src tests`
     - `uv run ty check src`
     - `uv run pytest`
     - `uv run pytest tests/benchmarks/test_smoke.py tests/benchmarks/test_smoke_benchmark_checks.py`
     - `pnpm --dir docs --ignore-workspace docs:generate-reference`
     - `pnpm --dir docs --ignore-workspace check`
     - `pnpm --dir docs --ignore-workspace build`
     - `scripts/lint.sh`
     - `uv build`
     - `uv run --with twine==6.2.0 twine check dist/*`

## Risks and Open Questions

- FL Studio is available locally, so release validation should include actual app launch and manipulation. CI still needs a live-harness for repeatable bridge-contract coverage when the DAW is not present.
- FastMCP task support is moving quickly. Re-check the latest docs and PyPI version immediately before implementation; task APIs and extras may have changed from the current `3.4.2` metadata.
- Adding a public discovery tool is justified by large-catalog ergonomics only if resources/templates are not enough. If added, it must be documented as a governed public API change.
- The current working tree is heavily dirty and should be cleaned as part of the release work. Cleanup still needs evidence-based classification so source changes are not accidentally discarded as debris.
- Publishing to PyPI/TestPyPI depends on external credentials and repository environment; local completion can verify build artifacts and workflow definitions, while actual publish success may need CI evidence.
