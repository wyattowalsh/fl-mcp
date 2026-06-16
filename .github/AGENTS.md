# AGENTS.md (.github scope)

Scope: .github/**

- Keep workflow changes tightly scoped and evidence-backed.
- Docs jobs must run the nested docs package with `pnpm --dir docs --ignore-workspace ...`.
- Do not reintroduce root npm package files just to simplify docs workflow commands.
- Python jobs should use `uv sync --all-extras --dev --locked` unless a concrete lockfile workflow requires otherwise.
- Keep release workflows aligned with uvx installability, package build checks, and docs build checks.
- When changing issue templates or PR templates, keep labels, prompts, and validation language consistent with the compact FastMCP surface and docs governance.
