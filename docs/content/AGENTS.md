# AGENTS.md (docs content scope)

Scope: docs/content/**

- MDX pages need frontmatter `title` and `description`.
- Do not use body-level `#` headings; page titles are rendered by the docs framework.
- Keep headings stable unless the link target is intentionally changing.
- Prefer concrete task paths, command blocks with language labels, and short verification checklists.
- Internal docs links should use `/docs/...` routes so `docs/scripts/check.mjs` can validate them.
- Generated files under `docs/content/docs/reference/generated/` must be produced by `docs/scripts/generate-reference.mjs`, not edited by hand.
- Keep the compact FastMCP public surface wording consistent with the public API inventory: 12 visible tools, 216 internal operations, 16 domains.
