# AGENTS.md (src scope)

Scope: src/**

## Runtime Contracts

- Strict typing is required for public contracts.
- Use Pydantic v2 models as the source of truth for request, response, resource, provider, bridge, and transaction schemas.
- Keep `src/fl_mcp/tools/fl_surface.py` as the internal FL operation catalog and `src/fl_mcp/tools/compact.py` as the compact agent-facing executor surface.
- Avoid public API sprawl. The default FastMCP server should expose the governed 12-tool compact surface unless the public API inventory is deliberately changed.

## Agent Surface

- Primitive FL operations must stay reachable through canonical `domain.operation` ids, not as individual visible MCP tools.
- Any operation/provider change must keep capability search, schema lookup, mock execution, provider metadata, safety/readback guidance, and generated docs aligned.
- Prefer resource reads and explicit readback over hidden state mutation.

## Validation

- For public-surface changes, run compact surface contract tests and inspect the visible FastMCP roster.
- For schema changes, regenerate and verify docs references.
