# CLAUDE.md

## Project mission constraints

1. Keep public MCP surface intentionally small.
2. Reads are resources-first.
3. Preserve one canonical project graph and one canonical transaction envelope.
4. Domain schemas are strongly typed.
5. Every mutation declares rollback/checkpoint class.

## Development expectations

- Prefer vertical slices that compile/test.
- Keep docs/generated references synced with code.
- Provider extensions must extend shared model rather than fork it.
