# Live Mode Safety

Live mode can mutate an actual FL Studio project. Treat it as a controlled
operation path, not a default.

## Live Intent Gate

Before any live mutation, require:

1. Setup Gate live output with `safe_to_attempt_live: true`.
2. User request clearly asks for live FL Studio work, or the user confirms live
   execution after seeing the plan.
3. Current project state is read through `fl_status`, `fl_snapshot`, or
   resources.
4. Every operation has schema-confirmed payloads and provider support details.

## Scratch-Project Safeguards

Use scratch or disposable projects for destructive or broad edits:

- delete, replace, clear, or overwrite operations;
- batch changes across many channels, mixer tracks, playlist items, or plugins;
- unknown plugin calibration or preset loading;
- render/export paths that could overwrite files.

If scratch state cannot be confirmed, rehearse in mock and return a live setup
checklist instead of mutating the DAW.

## Failure Handling

Report live failures as evidence, not as success:

- bridge timeout;
- `api_missing`;
- `unsupported_host_behavior`;
- `path_unavailable`;
- `host_exception`;
- provider unsupported;
- missing controller selection;
- no readback available.

Stop after a live failure unless the next step is read-only diagnosis.

## Claims

Allowed:

- "Mock rehearsal succeeded with provider `mock`."
- "Live operation was attempted and returned `unsupported_host_behavior`."
- "Live mutation succeeded and readback confirmed the new value."

Not allowed:

- "FL Studio changed" based only on mock results.
- "Render completed" based only on task creation.
- "Provider auto worked" without provider and bridge evidence.
