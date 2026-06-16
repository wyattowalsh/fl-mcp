# Setup Mode

Use Setup mode to prove FL MCP is available before planning, rehearsing, or
executing production workflows.

## Setup Gate

Run this check before every non-setup mode:

```bash
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode mock --source auto --repo-root . --format json
```

For live FL Studio work, run the live gate too:

```bash
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode live --source auto --repo-root . --format json
```

## JSON Fields

| Field | Meaning |
| --- | --- |
| `status` | `ok` or `blocked` |
| `source` | `local` checkout or `published` package |
| `mode` | `mock` or `live` |
| `checks[]` | Individual command/tool checks with command output |
| `client_config` | MCP stdio command shape for the chosen source |
| `missing_steps[]` | Actionable setup steps required before execution |
| `evidence[]` | Passed checks with command evidence |
| `safe_to_execute_mock` | Mock rehearsal can proceed |
| `safe_to_attempt_live` | Live FL Studio attempt can proceed if user intent is explicit |

## Minimum Readiness

Mock workflows require:

- `uv` and `uvx` available;
- `fl-mcp --version` succeeds through the selected source;
- `fl-mcp server run --mode stdio --dry-run` succeeds;
- `fl-mcp doctor --format json` succeeds.

Live workflows also require:

- `fl-mcp install --dry-run` succeeds;
- the reported bridge environment is configured in the MCP client;
- the FL Studio controller script is copied and selected when actual-app work is
  required.

## Degraded Output

Plan mode may continue when setup is blocked, but it must:

1. label the workflow as setup-degraded;
2. list `missing_steps[]` exactly;
3. avoid execution claims;
4. keep all live DAW steps behind explicit setup completion.

Rehearse, Execute, and Render must stop when the matching safe flag is false.

## Remediation Commands

Published package:

```bash
uvx fl-mcp --version
uvx fl-mcp server run --mode stdio --dry-run
uvx fl-mcp doctor --format json
uvx fl-mcp install --dry-run
```

Local checkout:

```bash
uvx --from /absolute/path/to/fl-mcp --with-editable /absolute/path/to/fl-mcp fl-mcp --version
uvx --from /absolute/path/to/fl-mcp --with-editable /absolute/path/to/fl-mcp fl-mcp server run --mode stdio --dry-run
uvx --from /absolute/path/to/fl-mcp --with-editable /absolute/path/to/fl-mcp fl-mcp doctor --format json
uvx --from /absolute/path/to/fl-mcp --with-editable /absolute/path/to/fl-mcp fl-mcp install --dry-run
```

Use the `client_config` JSON from setup output when wiring an MCP client.
