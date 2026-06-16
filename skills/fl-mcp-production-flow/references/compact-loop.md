# Compact Loop

FL MCP uses a compact FastMCP surface. Agents should not expect one visible MCP
tool per FL Studio primitive. Primitive DAW operations stay behind capability
search, schema lookup, execution tools, resources, and prompts.

## Loop

1. Orient with `fl_status`, `fl_snapshot`, or resources such as
   `runtime://capabilities` and `project://snapshot`.
2. Search the internal catalog with `fl_search_capabilities`.
3. Fetch the exact operation contract with `fl_get_capability_schema`.
4. Execute with `fl_execute`, `fl_batch_execute`, `fl_plan`, `fl_apply`,
   `fl_render`, or `fl_analyze_audio`.
5. Verify with readback, follow-up snapshot, task state, resources, or audio
   analysis.

## Boundaries

- Do not add or request new visible MCP tools to complete a production flow.
- Do not call primitive operation names as visible tools.
- Treat operation ids such as `mixer.set_track_volume` as payload values for
  `fl_execute` or `fl_batch_execute`.
- Treat current tool, operation, and domain counts as runtime facts to verify
  from `fl_status`, generated docs, or the public API inventory when needed.

## Provider Choice

| Situation | Provider |
| --- | --- |
| Rehearsal, CI, examples | `mock` |
| Live mode with explicit user intent | `auto` or schema-supported live provider |
| Comparing expected shape before live use | Start with `mock`, then repeat live only after setup passes |

In live mode, never infer success from a command being attempted. Require
provider and bridge evidence plus readback, task state, or explicit DAW result.
