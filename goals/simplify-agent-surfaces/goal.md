# FastMCP-Only Agentic Interface Closeout

Replace the broad visible MCP catalog with one compact, full-power FastMCP surface for FL Studio.
Agents should see an excellent DAW control console, not a dumped primitive API catalog.

## Final Target

- One supported FastMCP server surface only.
- Exactly 12 visible tools:
  `fl_status`, `fl_snapshot`, `fl_search_capabilities`, `fl_get_capability_schema`,
  `fl_execute`, `fl_batch_execute`, `fl_plan`, `fl_apply`, `fl_render`,
  `fl_analyze_audio`, `fl_manage_providers`, and `fl_browser`.
- The internal catalog remains full-power: 216 typed FL operations across 16 domains, plus any
  additional evidence-backed capabilities added later.
- Primitive FL operations are not visible as MCP tools. They are reached by canonical
  `domain.operation` ids through `fl_execute`, `fl_batch_execute`, capability resources, schema
  lookup, and workflow prompts.
- FastMCP is required; the minimal fallback and public/full surface flag are out of contract.

## Done Condition

- A FastMCP Client on `create_server(RuntimeConfig())` lists exactly the 12 visible tools and no
  primitive tools such as `fl_mixer_set_track_volume`.
- Every `FL_TOOL_SPECS` entry is discoverable, has an exact schema, and is executable through
  `fl_execute` in mock mode when a safe generated request exists.
- Common workflows are supported through the compact surface: status/snapshot, schema search,
  single execution, batch execution with readback, plan/apply, render/analyze, provider lifecycle,
  and browser-style plugin/preset/sample loading.
- Resources and prompts guide the agent loop: search capability, fetch schema, execute/plan/apply,
  then verify readback.
- Docs, public API inventory, OpenSpec change notes, and `BUILD_STATUS.md` describe the final
  12-tool compact surface and migration from primitive visible tools.
- Manual FastMCP smoke records visible tool count, internal operation count, representative
  cross-domain executions, batch workflow, render/audio task ids, and provider/task statuses.
