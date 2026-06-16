# Add FL MCP Production Flow Skill

## Goal

Add a repo-local, installable agent skill that helps AI agents operate FL MCP
production workflows safely through setup verification, mock rehearsal, compact
MCP execution, render/audio tasks, and evidence-backed verification.

## Boundaries

- Add only skill, skill references, setup-check script, evals, docs, and this
  governance record.
- Do not modify `src/fl_mcp/**`, `fl-bundle/**`, `alembic/**`, generated docs,
  database schemas, data pipelines, or docs app UI components.
- Keep the public MCP surface unchanged.

## Implementation Tasks

1. Add `skills/AGENTS.md` to define local skill-package rules.
2. Add `skills/fl-mcp-production-flow/SKILL.md` with setup, plan, rehearse,
   execute, render, audit, natural-language, and empty-args modes.
3. Add `scripts/setup-check.py` for JSON setup readiness checks.
4. Add references for setup, compact loop, recipes, live-mode safety, and
   validation evidence.
5. Add eval coverage for setup, production workflows, and negative routing.
6. Update README, AI workflows docs, and release notes.
7. Validate skill quality, docs, install discovery, and public-surface
   non-regression.

## Validation

```bash
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode mock --source local --repo-root . --format json
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode live --source local --repo-root . --format json
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile skills/fl-mcp-production-flow/scripts/setup-check.py
python3 -m json.tool skills/fl-mcp-production-flow/evals/evals.json >/dev/null
python3 <skill-creator>/scripts/audit.py skills/fl-mcp-production-flow/
npx skills add . --skill fl-mcp-production-flow --list
pnpm --dir docs --ignore-workspace lint
pnpm --dir docs --ignore-workspace check
pnpm --dir docs --ignore-workspace build
uv run pytest tests/contract/test_public_surface.py
uv run fastmcp inspect fastmcp.json --format mcp
git diff --check
```

If `wagents` is not project-local, use the configured harness `wagents` binary
with an explicit agents repository root and record the exact command path with
the validation evidence.

## Acceptance Criteria

- Setup mode exists and non-setup modes require the Setup Gate.
- Setup checker returns actionable JSON with missing setup steps.
- Skill install discovery finds `fl-mcp-production-flow`.
- Skill audit score is A/90+.
- Docs validation passes.
- Public FastMCP surface remains unchanged.
- Unrelated dirty paths are preserved.
