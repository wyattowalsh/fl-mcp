# FL MCP Docs

Fumadocs + Next.js documentation app.

## Commands

- `pnpm install --frozen-lockfile`
- `pnpm dev`
- `pnpm check`
- `pnpm docs:generate-reference`
- `pnpm docs:verify-reference`
- `pnpm lint`
- `pnpm build` (static export emitted under `out/`)

## Release Deploy Path

- Docs deploy workflow: `.github/workflows/docs-deploy.yml`
- Triggered by stable release tags and `workflow_dispatch`.
- Build pipeline verifies generated references, builds static site, and publishes `docs/out` to GitHub Pages.
