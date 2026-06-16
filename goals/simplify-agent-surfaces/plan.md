# FastMCP-Only Agentic Interface Closeout Plan

## Decisions

- Use FastMCP all the time. Do not keep `MinimalMCPServer`, `RuntimeConfig.surface`, `--surface`,
  public/full branching, or visible primitive tool registration.
- Keep all FL power underneath the compact surface. Full power means every internal operation is
  discoverable and executable, not that every primitive is listed as an MCP tool.
- Use canonical operation ids in the form `domain.operation`, for example
  `mixer.set_track_volume`.
- Use Ableton-MCP as workflow inspiration for DAW browser, plugin/preset/sample loading,
  arrangement workflows, and musical task prompts. Do not copy its flat one-action tool model.
- Use FastMCP 3.4.2 features present in this repo: server `instructions`, tool titles,
  descriptions, tags, annotations, output schemas, first-class prompts, resources/templates,
  in-memory `Client` smoke, and Context logging/progress.

## Implementation Scope

1. Keep `FL_TOOL_SPECS`, `FL_TOOL_HANDLERS`, provider routing, mock/live behavior, task metadata,
   and operation metadata as the internal catalog.
2. Register exactly 12 visible tools:
   `fl_status`, `fl_snapshot`, `fl_search_capabilities`, `fl_get_capability_schema`,
   `fl_execute`, `fl_batch_execute`, `fl_plan`, `fl_apply`, `fl_render`,
   `fl_analyze_audio`, `fl_manage_providers`, and `fl_browser`.
3. Provide schema-first discovery:
   search capabilities, fetch schema/examples/provider support/safety/readback guidance, then
   execute by operation id.
4. Keep resources-first reads:
   `runtime://health`, `runtime://capabilities`, `providers://matrix`, `project://snapshot`,
   `project://arrangement`, and task/domain templates.
5. Register workflow prompts:
   diagnostics, transaction guidance, build beat, browser loading, automation, arrangement, safe
   mix adjustment, and render/analyze.
6. Update docs/governance:
   README, architecture overview, public API inventory, release notes, OpenSpec change,
   `BUILD_STATUS.md`, and this goal package.

## Validation

- Focused contract suite:
  `uv run python -m pytest tests/contract/test_public_surface.py tests/unit/test_server_factory_auth_bootstrap.py tests/unit/test_server_creation.py tests/integration/test_cli_edge_cases.py tests/unit/test_imports.py -q`
- Manual FastMCP Client compact-surface smoke:
  list tools, search capabilities, fetch schemas, execute representative operations across all
  domains, run a batch workflow, run render/audio tasks, and record counts/statuses/task ids.
- FastMCP inspect:
  `uv run fastmcp inspect fastmcp.json --format mcp -o /tmp/fl-mcp-fastmcp-inspect-output.json`
- Broader gates as time permits:
  `scripts/lint.sh`, `uv run pytest`, docs reference/check/build, OpenSpec validate, and build/twine
  checks.

## Current Known External Limit

Live in-FL callback polling still depends on FL Studio loading the installed controller script in
the active session. The compact surface is validated in deterministic mock mode and through the
repo-owned bridge contracts; live provider expansion remains evidence-gated.
