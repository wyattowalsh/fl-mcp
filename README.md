# fl-mcp

`fl-mcp` is a local-first MCP server scaffold for FL Studio with a resources-first public surface,
transaction-oriented mutation model, and a docs portal built on Next.js + Fumadocs.

## Monorepo Layout

- `src/fl_mcp/`: Python runtime, schemas, transactions, tools, resources, and CLI.
- `docs/`: Next.js/Fumadocs docs app and generated references.
- `fl-bundle/`: FL-side bundle scaffold (controller, piano roll, VFX, shared assets).
- `helper/`: macOS helper app scaffold.
- `providers/`: provider templates and provider package space.

## Local Development

### Python runtime

```bash
uv sync --all-extras --dev
uv run pytest -q
```

### CLI

```bash
uv run fl-mcp --help
uv run fl-mcp doctor
uv run fl-mcp diagnostics shell
uv run fl-mcp server run --mode stdio
```

### Docs app

```bash
pnpm --dir docs install --no-frozen-lockfile
pnpm --dir docs docs:generate-reference
pnpm --dir docs dev
```

## CI and Release

- CI gates: tests, docs build/reference sync, pre-commit, dependency audit.
- Security gate: scheduled vulnerability + license checks.
- Release workflows: prerelease and stable pipelines with artifact publishing.

## Architecture Governance

- Public API inventory: `docs/content/docs/architecture/public-api-inventory.mdx`
- Reuse audit: `docs/content/docs/architecture/reuse-audit.mdx`
- Build/status ledger: `BUILD_STATUS.md`
