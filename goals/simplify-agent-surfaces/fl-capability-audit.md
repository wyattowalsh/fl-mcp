# FL Capability Audit

This audit tracks how FL Studio capabilities are agentically enabled after the compact
FastMCP closeout.

## Current Coverage

The internal catalog contains 216 typed operations across 16 domains:

- `arrangement`: 5
- `audio`: 3
- `automation`: 7
- `channels`: 26
- `connection`: 2
- `device`: 5
- `general`: 19
- `midi`: 5
- `mixer`: 30
- `patterns`: 10
- `piano-roll`: 10
- `playlist`: 18
- `plugins`: 38
- `render`: 3
- `transport`: 21
- `ui`: 14

Each operation is reachable through:

- `fl_search_capabilities`
- `fl_get_capability_schema`
- `fl_execute`
- `fl_batch_execute`
- `runtime://capabilities`
- `runtime://capabilities/{domain}`

## Provider State

- `mock`: full 216-operation coverage for deterministic tests and local agent workflows.
- `flapi-live`: safe shipped live subset for current general/transport host support.
- `piano-roll-script`: piano-roll scripting path for supported note workflows.
- `midi-fallback`: bounded MIDI/SysEx style fallback for supported control surfaces.

Capabilities without current live host support remain safely mock-backed and provider-documented
until a live adapter implements the exact operation.

## Browser And Workflow Enablement

`fl_browser` covers Ableton-inspired asset workflows over FL-specific operations:

- plugin list/load/replace,
- preset navigation and named preset loading,
- channel sample loading,
- pattern and piano-roll workflow starters,
- playlist placement and browser window visibility.

Workflow prompts cover:

- build beat,
- load instrument/effect,
- create automation,
- arrange sections,
- safe mix adjustment,
- render and analyze.

## Blocked Or Unsafe Classes

No new visible MCP tools are required for blocked/unsafe classes. Future additions should use one
of these routes:

- add a typed operation to `FL_TOOL_SPECS` with provider/safety/readback metadata,
- add a resource/template for read-only discovery,
- add a workflow prompt for guided use,
- document the class here as blocked by FL Studio host limitations or safety constraints.

## Validation Snapshot

Release-candidate FastMCP Client smoke on 2026-06-16:

- visible tool count: 12,
- internal operation count: 216,
- representative `fl_execute` calls succeeded across all 16 domains in mock mode with provider `mock`,
- `fl_batch_execute` succeeded for a tempo/volume/pattern workflow (`succeeded=3`, `failed=0`, providers `mock/mock/mock`),
- render task id: `mock-3addaabfdaeddf63`,
- audio task id: `mock-0f3ddd488da078c9`,
- browser plugin search returned 4 results and browser plugin load used `plugins.load` with provider `mock`.
