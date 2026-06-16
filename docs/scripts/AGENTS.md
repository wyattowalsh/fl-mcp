# AGENTS.md (docs scripts scope)

Scope: docs/scripts/**

- Scripts must run from `docs/` as the working directory and should not depend on a root `package.json`.
- Keep scripts compatible with `pnpm --dir docs --ignore-workspace ...` and the pinned package manager in `docs/package.json`.
- `check.mjs` is the docs health gate for frontmatter, heading sanity, generated reference drift, and internal `/docs/...` links.
- `generate-reference.mjs` is the only writer for `docs/content/docs/reference/generated/`.
- `build.mjs` should run the docs health gate before `next build`.
- Avoid shell-specific syntax in Node scripts; use `spawnSync` / `spawn` with argument arrays.
