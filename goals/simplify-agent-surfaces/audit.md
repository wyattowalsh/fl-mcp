# FastMCP-Only Agentic Surface Audit

**Goal**: `goals/simplify-agent-surfaces`
**Current target**: one compact full-power FastMCP surface
**Visible tool count**: 12
**Internal operation count**: 216 operations across 16 domains

## Final Surface

Visible MCP tools:

- `fl_status`
- `fl_snapshot`
- `fl_search_capabilities`
- `fl_get_capability_schema`
- `fl_execute`
- `fl_batch_execute`
- `fl_plan`
- `fl_apply`
- `fl_render`
- `fl_analyze_audio`
- `fl_manage_providers`
- `fl_browser`

Primitive operation tools such as `fl_mixer_set_track_volume`, `mixer_set_track_volume`,
`channels_list`, or `transport_get_state` are no longer visible MCP tools. They remain
reachable by canonical operation ids, for example `mixer.set_track_volume`, through
`fl_execute` and `fl_batch_execute`.

## Internal Catalog

| Domain | Count |
| --- | ---: |
| `arrangement` | 5 |
| `audio` | 3 |
| `automation` | 7 |
| `channels` | 26 |
| `connection` | 2 |
| `device` | 5 |
| `general` | 19 |
| `midi` | 5 |
| `mixer` | 30 |
| `patterns` | 10 |
| `piano-roll` | 10 |
| `playlist` | 18 |
| `plugins` | 38 |
| `render` | 3 |
| `transport` | 21 |
| `ui` | 14 |

Every `FL_TOOL_SPECS` entry is represented in capability search, schema lookup, resource
serialization, and mock execution through the compact executor.

## Ableton-MCP Lessons Applied

- Keep the DAW-facing surface workflow-oriented instead of exposing every low-level API as a
  separate visible tool.
- Provide browser-style discovery and loading flows for plugins, presets, samples, drum kits, and
  arrangement assets.
- Treat long-running render/audio/import workflows as task-like operations with clear status
  metadata.
- Keep raw command depth behind a typed catalog and schema lookup rather than a flat one-action
  tool list.

## FastMCP Alignment

- FastMCP is required. The minimal fallback server and public/full surface flag are removed from
  the supported server contract.
- The server uses FastMCP instructions to teach the loop:
  status/snapshot -> search -> schema -> execute/batch/plan/apply -> readback verification.
- Tool registration includes titles, descriptions, tags, annotations, output schemas, and native
  task metadata for render/audio entrypoints.
- Context logging/progress is enabled around batch, render, audio analysis, provider lifecycle,
  and browser workflows.

## Verification

- Focused contract/unit/integration suite:
  `uv run python -m pytest tests/contract/test_public_surface.py tests/contract/test_resource_and_schema_contracts.py tests/unit/test_server_factory_auth_bootstrap.py tests/unit/test_server_creation.py tests/integration/test_cli_edge_cases.py tests/unit/test_imports.py -q`
  passed.
- Manual FastMCP Client smoke:
  - `list_tools`: 12 visible tools.
  - Internal operation count from `fl_status`: 216.
  - Search/schema: `mixer.set_track_volume` schema resolved as `MixerTrackVolumeRequest`.
  - Cross-domain `fl_execute`: 16/16 domains returned structured mock results with provider `mock`.
  - `fl_batch_execute`: 3-step tempo/volume/pattern workflow succeeded with readback policy and providers `mock/mock/mock`.
  - `fl_render` task id: `mock-3addaabfdaeddf63`.
  - `fl_analyze_audio` task id: `mock-0f3ddd488da078c9`.
  - `fl_browser` plugin search returned 4 results and plugin load used `plugins.load` with provider `mock`.

## Closed Decisions

- No separate minimal/public/full surfaces.
- No visible primitive FL MCP tools.
- No 16 domain dispatcher tools.
- Full power lives in the internal catalog and typed operation ids.
- New evidence-backed capabilities should be added to the internal catalog, resources, schemas, or
  prompts, not as new visible primitive tools.
