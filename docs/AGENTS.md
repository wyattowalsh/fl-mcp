# AGENTS.md (docs scope)

Scope: docs/**

## Framework

- This docs tree is a Fumadocs + Next.js app with its own package metadata under `docs/`.
- Use `pnpm --dir docs --ignore-workspace ...` from the repository root so commands do not climb into parent pnpm workspaces.
- Keep JavaScript/TypeScript docs files nested here: `docs/package.json`, `docs/pnpm-lock.yaml`, `docs/tsconfig.json`, `docs/next.config.mjs`, `docs/source.config.ts`, `docs/scripts/**`, and `docs/app/**`.
- `docs/pnpm-lock.yaml` is the authoritative pnpm lockfile. Do not recreate root-level npm package files or a root `Makefile` for docs shortcuts.

## Content

- Prefer concise MDX pages with stable headings, frontmatter `title`, and frontmatter `description`.
- Use source-grounded statements. For current surface counts, verify against `src/fl_mcp/server/factory.py` and `src/fl_mcp/tools/fl_surface.py`.
- Architecture pages must align with the compact FastMCP surface, canonical graph, provider routing, bridge protocol, and transaction envelope.
- Client docs should teach the agent loop: status or snapshot -> search capabilities -> fetch schema -> execute/batch/plan/apply -> verify readback or snapshot.
- Use `uvx` as the normal install/client path. Use `uv run` only for repository development commands.

## Generated Files

- Generated JSON schemas belong in `docs/generated/schemas`.
- Generated reference MDX belongs in `docs/content/docs/reference/generated`.
- Generated Fumadocs files under `docs/.source`, Next build output under `docs/.next`, static output under `docs/out`, and `docs/tsconfig.tsbuildinfo` are disposable build artifacts.
- Generated artifacts should not be hand-edited.

## Validation

- For prose-only docs changes, run `pnpm --dir docs --ignore-workspace check`.
- For MDX structure, scripts, package metadata, layout, or navigation changes, run:
  - `pnpm --dir docs --ignore-workspace lint`
  - `pnpm --dir docs --ignore-workspace check`
  - `pnpm --dir docs --ignore-workspace build`
