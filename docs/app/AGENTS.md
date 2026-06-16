# AGENTS.md (docs app scope)

Scope: docs/app/**

- This is the Fumadocs + Next.js presentation layer. Keep content in `docs/content/docs/` unless the change is layout, navigation, metadata, or styling.
- Keep the landing page focused on the docs experience, not a marketing site.
- Preserve accessible navigation: skip link, semantic sections, readable focus states, and stable route targets.
- Use routes from the Fumadocs content graph and avoid hardcoding links to generated build artifacts.
- Validate app/layout changes with `pnpm --dir docs --ignore-workspace lint` and `pnpm --dir docs --ignore-workspace build`.
