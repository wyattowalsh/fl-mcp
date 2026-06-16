# AGENTS.md (root)

Scope: entire repository unless overridden by nested AGENTS.md.

## Public Surface Guardrails

- Do not add public MCP tools unless clearly justified and documented in public API inventory.
- The supported server surface is the compact FastMCP surface: 12 visible tools backed by the internal FL operation catalog. Primitive FL operations stay behind `fl_execute`, `fl_batch_execute`, capability search, schemas, resources, and prompts.
- Keep resources-first read pathways. Prefer `fl_status`, `fl_snapshot`, `runtime://capabilities`, `project://snapshot`, and provider resources for orientation before mutation.
- Use strongly typed Pydantic v2 models for schema contracts.
- Keep capability, schema, provider, and safety metadata in sync when changing operations or provider routing.

## Documentation And Release Notes

- After public API, file layout, docs tooling, bridge behavior, agent instructions, or install commands change, update the relevant docs in the same change set.
- Agent skill changes under `skills/` must follow `skills/AGENTS.md` and keep README, release notes, workflow docs, evals, and install-discovery guidance aligned.
- Use `goals/`, release notes, and the public API inventory for change/governance records in this tree. Do not reference removed root ledgers unless they are restored.
- Regenerate generated reference docs with `pnpm --dir docs --ignore-workspace docs:generate-reference`; do not hand-edit files under `docs/content/docs/reference/generated/`.
- The JavaScript/TypeScript docs package is nested under `docs/`. Do not recreate root `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, or `Makefile` docs aliases.

## Validation

- For docs changes, run `pnpm --dir docs --ignore-workspace check`; run `lint` and `build` when MDX, docs scripts, package metadata, or layout changes.
- For public-surface changes, also run focused FastMCP/server tests and a compact surface smoke before claiming completion.
- Preserve unrelated dirty work. This repository often has concurrent release-prep changes in flight.
