# AGENTS.md (fl-bundle scope)

Scope: fl-bundle/**

## FL Studio Bundle Rules

- Bundle files must remain installable by the CLI and understandable to FL Studio users.
- Keep scripts modular for per-surface debugging: controller, piano-roll, VFX, shared helpers, and shared assets should remain separable.
- Do not move server orchestration logic into FL Studio scripts. The DAW-side code should translate a narrow, typed request into FL Studio API calls and return typed responses.
- Preserve host bridge safety: private bridge directory, no symlink trust, current-user ownership, and predictable request/response filenames.
- Keep live operation claims narrow and evidence-backed. If an operation is mock-only or harness-only, document it that way.

## Validation

- When controller bridge files change, run the bridge/unit tests that exercise the host-file protocol and update bridge protocol docs.
- If a manual FL Studio smoke is performed, record exact controller, bridge directory, request id, operation id, and result.
