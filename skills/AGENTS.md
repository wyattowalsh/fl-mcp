# AGENTS.md (skills scope)

Scope: skills/**

## Skill Package Rules

- Keep each skill as a raw `SKILL.md` package with optional one-level
  `references/`, `scripts/`, `templates/`, and `evals/` children.
- Do not add public MCP tools, resources, prompts, providers, schemas, or server
  runtime behavior from skill work. Skills guide agents; they do not expand the
  FastMCP public surface.
- Every skill must have a dispatch table, empty-args behavior, scope boundaries,
  critical rules, and a reference file index when references exist.
- Every reference file listed in `SKILL.md` must exist. Do not leave orphan
  references that are not listed.
- Scripts must use `argparse`, write machine-readable JSON to stdout, and write
  diagnostics to stderr.

## Validation

- Validate repo-local skill packages from this checkout with setup-check
  scripts, JSON syntax checks, skill-creator audit, and `npx skills add .
  --skill <name> --list`.
- Do not run centralized `wagents validate` from this repository unless it has
  been wired as a wagents repository. When reconciling the external agents
  harness, point `wagents` at that agents repository explicitly and record the
  exact command.
- Run the skill-creator audit for the changed skill before declaring it ready.
- Preview installability with `npx skills add . --skill <name> --list`.
- If skill changes alter docs, install commands, or file layout, update README,
  release notes, and docs in the same change set.
