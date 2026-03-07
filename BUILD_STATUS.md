# BUILD STATUS

Integration marshal: codex-main

| task id | owner/subagent | status | dependencies | blockers | touched paths | merge notes |
|---|---|---|---|---|---|---|
| T00 | codex-main | completed | none | none | root, src/, docs/, tests/, providers/, helper/, fl-bundle/ | Initial scaffold complete |
| T01 | codex-main | completed | T00 | none | README.md, LICENSE, CHANGELOG.md, .editorconfig, .gitignore, .gitattributes, .python-version | Naming aligned to fl-mcp |
| T02 | codex-main | completed | T00 | none | CLAUDE.md, AGENTS.md, .claude/**, scoped AGENTS.md | AI instruction system in place |
| T03 | codex-main | completed | T00 | none | .github/**, adr/template.md, docs/templates/design-proposal.md | Governance templates added |
| T04 | codex-main | completed | T00 | none | .pre-commit-config.yaml, pyproject tooling config | Local quality tooling set |
| T10 | codex-main | completed | T00 | none | src/fl_mcp/server, src/fl_mcp/runtime | stdio/http server shell added |
| T11-T14 | codex-main | completed | T10 | none | src/fl_mcp/config, logging, middleware, auth, transforms, prompts, apps | Runtime foundation shell complete |
| T20-T24 | codex-main | completed | T10 | none | src/fl_mcp/schemas, graph, transactions, persistence | Canonical schema/graph/transactions/persistence baseline |
| T30-T34 | codex-main | completed | T20 | none | src/fl_mcp/resources, tools | Public MCP surface baseline |
| T40-T43 | codex-main | completed | T20 | none | src/fl_mcp/bridge, fl-bundle/, cli doctor/install | Bridge + bundle + diagnostics shell |
| T50-T57 | codex-main | completed | T21 | none | src/fl_mcp/graph/domains.py | Domain graph skeleton in canonical model |
| T60-T64 | codex-main | completed | T20 | none | src/fl_mcp/providers, providers/template_provider | Provider runtime + SDK shell + templates |
| T70-T72 | codex-main | completed | T00 | none | docs/** | Docs portal + flagship IA content |
| T73-T74 | codex-main | completed | T40 | none | helper/FLMCPHelper | Thin SwiftUI helper shell + integration notes |
| T80-T83 | codex-main | completed | all prior | none | tests/, .github/workflows, release configs | Tests/CI/release baseline |
| T90 | codex-main | completed | all | none | BUILD_STATUS.md + architecture docs | Integration marshal guardrails maintained |
