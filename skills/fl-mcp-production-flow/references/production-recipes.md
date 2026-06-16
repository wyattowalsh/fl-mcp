# Production Recipes

Each recipe starts with Setup Gate, then uses the compact loop.

## Beat Or Arrangement Plan

1. Run Setup Gate.
2. Read project state with `fl_snapshot`.
3. Search arrangement, pattern, playlist, channel, and transport capabilities.
4. Fetch schemas for each chosen operation.
5. Use `fl_plan` for multi-step edits when rollback or ordering matters.
6. Apply with readback after each meaningful stage.

## Mock Rehearsal

1. Require `safe_to_execute_mock: true`.
2. Use explicit `provider="mock"`.
3. Execute representative read/set/readback sequences.
4. Record operation ids, payloads, and result shapes.
5. Carry only schema-confirmed payloads into live planning.

## Plugin Or Preset Workflow

1. Use `fl_browser` for plugin, preset, sample, or asset discovery.
2. Search `plugins` capabilities for semantic profile or raw parameter work.
3. Fetch schemas for profile lookup, instance probing, calibration, and mapped
   parameter operations.
4. Treat semantic profile seeds as mapping intent, not proof of live parameter
   indices.
5. Stop on `calibration_required`, `parameter_unmapped`, `plugin_not_installed`,
   or `preset_unavailable` and report the exact next calibration step.

## Automation Workflow

1. Search automation capabilities by target parameter and domain.
2. Fetch schema for automation clip or parameter operation.
3. In live mode, confirm the plugin/channel/track target by readback or
   snapshot before mutation.
4. Use batch execution for ordered create/set/readback steps.

## Render And Analyze

1. Run Setup Gate for mock or live target.
2. Call `fl_render` with schema-confirmed request fields.
3. Record task id, provider, bridge mode, output path, and status.
4. Use `fl_analyze_audio` on the exported artifact when quality evidence is
   needed.
5. Verify via task resources or follow-up status; task creation alone is not
   completion.

## Evidence Audit

Use Audit mode after any workflow:

- separate mock from live evidence;
- list operation ids, request ids, providers, bridge modes, and task ids;
- cite readback or snapshot evidence;
- report missing setup or verification steps before claiming completion.
