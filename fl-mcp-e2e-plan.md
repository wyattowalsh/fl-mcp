
# FL MCP — End-to-End Build Plan

## 1. Product definition

**Brand**
- FL MCP

**Canonical names**
- GitHub repo: `fl-mcp`
- PyPI package: `fl-mcp`
- Python import: `fl_mcp`
- MCP server name: `fl-mcp`
- Helper app: `FL MCP Helper`

**Mission**
Build the best general-purpose FL Studio MCP currently possible:
- deep coverage across every feasible FL Studio surface in `0.1.0`
- small, purpose-driven public MCP surface
- rich internal capability model
- transactional mutation model
- stable provider API from day 1
- flagship docs portal
- repo ergonomics optimized for AI coding agents and parallel subagents

**Delivery scope**
- local-only OSS for `0.1.x`
- official client support/testing for Claude Code, Codex, Gemini CLI, and GitHub Copilot
- transports: `stdio` + streamable HTTP
- unified CLI
- macOS helper app
- heavily customized Fumadocs docs site
- CI/CD, pre-commit, templates, ADRs, examples, provider templates, release automation

## 2. Locked architecture decisions

### Runtime and repo shape
- Typical FastMCP-style Python repo with top-level `/docs`
- Python 3.12+
- `uv` + `pyproject.toml`
- `pnpm` for docs/tooling
- core implementation in Python
- TypeScript only where clearly best: docs/tooling
- helper app in Swift/SwiftUI on macOS

### Public contract
- Resources-first for reads
- Small, purpose-driven public tool surface
- Generic `query_project`
- Generic `plan_changes`
- Generic `apply_changes`
- Minimal additional tools only when materially clearer than generic plan/apply
- Canonical transaction envelope with strongly typed domain payloads
- Canonical project graph

### Safety and mutation
- Transactional mutations with preview, checkpoints, rollback metadata, and policy-driven partial/all-or-nothing execution
- Mutation classes:
  - `fully_transactional`
  - `checkpointed`
  - `best_effort`
  - `unsafe_raw`
- Hybrid rollback:
  - FL-native undo/history where available
  - checkpoint/snapshot overlay elsewhere

### State model
- Snapshot-first canonical model
- On-demand refresh available
- Incremental live updates when available
- Domain resources are projections from the canonical graph

### Transport and FL integration
- Primary orchestration via local loopback control plane
- MIDI only where FL requires it
- Unified default FL-side install bundle
- Optional advanced per-surface installs for debugging and tests

### Extensibility
- Stable provider API from day 1
- In-process Python providers only in `0.1.x`
- One package per provider/plugin
- Official provider suite shipped as separate packages

### Persistence and operations
- SQLite
- Pydantic v2
- Pydantic Settings
- SQLModel
- Alembic
- Loguru with structured JSON logs + rich local console output
- Async-heavy internals, with sync-friendly facades where useful

### Docs and DX
- Fumadocs, heavily customized
- Orama search
- Lightweight docs versioning from day 1
- Root `CLAUDE.md` + root and nested `AGENTS.md`
- `.claude/agents`, `.claude/commands`, `.claude/hooks`, `.claude/output-styles`, `.claude/playbooks`, `.claude/templates`

### Release and governance
- MIT
- trunk-based development
- prereleases + stable releases
- Conventional Commits + automated changelog
- CI on Linux + macOS + Windows
- release gates include code/tests/docs + security/license/dependency checks
- Renovate for dependency automation
- experimental features on by default, but maturity-labeled and isolated

## 3. Product principles

1. No public tool sprawl.
2. Resources-first for reads.
3. One canonical project graph.
4. One canonical transaction envelope.
5. Domain schemas must be strongly typed.
6. Every mutation declares rollback/checkpoint class.
7. MIDI is an edge transport, not the orchestration backbone.
8. Providers extend the shared model; they do not fork it.
9. Generated docs/reference stay synced with code.
10. Experimental features can be on by default, but must be clearly maturity-labeled.
11. The helper app stays thin.
12. The public API stays smaller than the internal capability graph.

## 4. Public MCP surface

### Primary resources
- `project://snapshot`
- `project://summary`
- `project://domains/transport`
- `project://domains/mixer`
- `project://domains/channels`
- `project://domains/patterns`
- `project://domains/piano-roll`
- `project://domains/plugins`
- `project://domains/vfx`
- `project://domains/audio`
- `runtime://health`
- `runtime://diagnostics`
- `runtime://config`
- `transactions://recent`
- `checkpoints://recent`
- `providers://installed`
- `schemas://public`

### Primary tools
- `query_project`
- `plan_changes`
- `apply_changes`
- `render_project`
- `analyze_audio`
- `inspect_runtime`
- `manage_providers`

### Optional ergonomic tools
Only if clearly justified:
- `checkpoint_project`
- `rollback_transaction`
- `preview_transaction`
- `create_musical_content`

## 5. Transaction envelope

### Phases
1. intent
2. preconditions
3. plan compilation
4. validation
5. diff/preview
6. checkpoint
7. apply
8. post-apply verification
9. rollback/report
10. audit log

### Envelope shape
- schema version
- request id
- mode: preview/apply
- execution policy: all-or-nothing or allow-partial
- safety mode
- freshness policy
- target snapshot id
- typed domain changes
- preconditions
- metadata

### Result shape
- transaction id
- status
- checkpoint id
- snapshot before/after
- per-domain results
- diff summary
- rollback capability
- warnings
- errors

## 6. Canonical project graph

### Domains
- project metadata
- transport/session
- mixer graph
- channels/instruments
- patterns/playlist
- piano roll note graph
- plugin parameter graph
- VFX/Patcher graph
- audio render/artifact graph
- transactions/checkpoints/audit

### Rules
- one graph only
- snapshot-based, versioned
- typed and serializable
- graph is the internal source of truth
- resources are projections from the graph
- mutations reference graph targets rather than ad hoc state

## 7. FL integration model

### Unified FL bundle
Default bundle includes:
- controller scripting integration
- piano-roll scripting integration
- VFX/Patcher integration where feasible
- bridge config/files
- diagnostics hooks
- installer assets

### Transport policy
- loopback IPC/HTTP/WebSocket style control plane for orchestration and diagnostics
- MIDI isolated behind adapters where FL requires it

### Rollback/checkpoint policy
- prefer FL-native undo/history when available
- overlay with explicit checkpoints and snapshot metadata

### Deep coverage target before `0.1.0`
- transport
- mixer
- channels/instruments
- patterns/playlist
- piano roll
- plugins/parameters
- VFX/Patcher
- audio/render/export
- runtime diagnostics and health

## 8. FastMCP v3 usage map

Use the full useful FastMCP surface:
- tools
- resources
- prompts
- middleware
- transforms
- authorization
- apps/UI

### How each is used
- **Resources**: primary read interface
- **Tools**: small public action/query surface
- **Prompts**: install, troubleshooting, workflow, provider-authoring, safety guidance
- **Middleware**: logging, timing, auth, safety gating, exception normalization, audit hooks
- **Transforms**: client-specific shaping where beneficial
- **Authorization**: optional token/auth for local HTTP mode, plus policy gating
- **Apps/UI**: diagnostics inspector, transaction preview/apply, runtime inspector

## 9. Provider and SDK strategy

### Stable provider API
Providers may:
- add resources
- add mutation handlers inside the shared transaction model
- contribute schemas
- contribute docs metadata
- contribute prompts/examples

Providers may not:
- fork the core transaction model
- explode the public tool surface arbitrarily
- run out-of-process in `0.1.x`

### Packaging
- one package per provider
- official suite:
  - `fl-mcp-provider-style-memory`
  - `fl-mcp-provider-audio-analysis`
  - `fl-mcp-provider-export-tools`

### SDKs
- Python provider SDK
- Typed client SDK
- codegen/template exports
- manifest-driven discovery

## 10. Reuse strategy for existing FL Studio MCP servers

Reference sources:
- `veenastudio/flstudio-mcp`
- `ohhalim/flstudio-mcp`
- `calvinw/fl-studio-mcp`
- `karl-andres/fl-studio-mcp`
- `szichedelic/fl-studio-mcp`
- `fruityloops-mcp`
- `iflow-mcp-ohhalim-flstudio-mcp`

### Reuse policy
**Always reuse if helpful**
- install/setup ideas
- diagnostics ideas
- FL-side script layout patterns
- state export patterns
- test scenarios
- compatibility notes
- docs patterns

**Reuse only if legally safe and architecturally coherent**
- utility modules
- install scripts
- helper functions
- bridge helpers
- test fixtures
- schemas

**Do not inherit**
- bloated public tool surfaces
- architecture assumptions that overfit one FL surface
- abstractions that weaken the transaction model
- incoherent implementation shortcuts

### Key takeaways
- Veena/Ohhalim: valuable for minimal FL bridge patterns and controller/MIDI fallback concepts
- Calvinw: valuable for structured state export and deterministic piano-roll flows
- Karl-Andres: valuable for broad coverage ambition and installer ergonomics
- Szichedelic: valuable for bridge separation and runtime-vs-FL boundary clarity
- Fruityloops-MCP / Flapi path: useful as optional backend ideas, not the architectural center
- Ohhalim RAG path: should live as a provider/plugin lane, not core runtime

## 11. Repository structure

```text
fl-mcp/
├─ pyproject.toml
├─ uv.lock
├─ package.json
├─ pnpm-workspace.yaml
├─ fastmcp.json
├─ README.md
├─ LICENSE
├─ CHANGELOG.md
├─ CLAUDE.md
├─ AGENTS.md
├─ .pre-commit-config.yaml
├─ .github/
│  ├─ workflows/
│  ├─ ISSUE_TEMPLATE/
│  ├─ PULL_REQUEST_TEMPLATE/
│  └─ CODEOWNERS
├─ .claude/
│  ├─ agents/
│  ├─ commands/
│  ├─ hooks/
│  ├─ output-styles/
│  ├─ playbooks/
│  └─ templates/
├─ docs/
│  ├─ app/
│  ├─ content/
│  ├─ components/
│  ├─ lib/
│  ├─ generated/
│  ├─ public/
│  └─ package.json
├─ src/fl_mcp/
│  ├─ cli/
│  ├─ config/
│  ├─ logging/
│  ├─ runtime/
│  ├─ server/
│  ├─ resources/
│  ├─ tools/
│  ├─ prompts/
│  ├─ apps/
│  ├─ middleware/
│  ├─ auth/
│  ├─ transforms/
│  ├─ transactions/
│  ├─ graph/
│  ├─ domains/
│  │  ├─ transport/
│  │  ├─ mixer/
│  │  ├─ channels/
│  │  ├─ patterns/
│  │  ├─ piano_roll/
│  │  ├─ plugins/
│  │  ├─ vfx/
│  │  └─ audio/
│  ├─ bridge/
│  ├─ fl_bundle/
│  ├─ providers/
│  ├─ sdk/
│  ├─ persistence/
│  ├─ schemas/
│  └─ compat/
├─ providers/
│  ├─ style-memory/
│  ├─ audio-analysis/
│  ├─ export-tools/
│  └─ templates/
├─ helper/
│  └─ macos/
├─ fl-bundle/
│  ├─ controller/
│  ├─ piano-roll/
│  ├─ vfx/
│  ├─ shared/
│  └─ installer/
├─ examples/
│  ├─ clients/
│  ├─ providers/
│  ├─ workflows/
│  └─ sample-projects/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ contracts/
│  ├─ schema/
│  ├─ fixtures/
│  ├─ snapshots/
│  └─ e2e/
├─ scripts/
├─ adr/
└─ generated/
```

## 12. CLI and helper

### Unified CLI
- `fl-mcp install`
- `fl-mcp doctor`
- `fl-mcp run`
- `fl-mcp config show`
- `fl-mcp config edit`
- `fl-mcp providers list`
- `fl-mcp providers install`
- `fl-mcp providers validate`
- `fl-mcp logs tail`
- `fl-mcp helper open`
- `fl-mcp docs dev`
- `fl-mcp export bundle`

### Helper app
Responsibilities:
- install/setup assistance
- runtime status
- bridge health
- diagnostics
- logs viewer
- quick actions

Not responsibilities:
- main automation surface
- full workflow editor
- giant settings universe

## 13. Docs portal

### Stack
- Next.js App Router
- Fumadocs
- Fumadocs Python integration where useful
- Orama
- generated schema/reference pages
- heavily customized branded UI

### IA
- Home
- Getting Started
- Installation
- Concepts
- Guides
- API & Schemas
- Providers
- Clients
- Helper App
- Architecture
- ADRs
- Security
- Troubleshooting
- Release Notes
- Roadmap
- Contributing
- Agent Teams & AI Workflows

### Special pages
- comparison vs existing FL Studio MCP servers
- why transactional mutation
- why resources-first
- project graph model
- checkpoint/rollback semantics
- provider authoring guide
- client setup guides
- helper app docs
- local HTTP security docs
- feature maturity matrix

## 14. AI execution model

### Execution strategy
Adaptive:
- single-agent for cheap focused work
- subagents for medium bounded work
- agent teams for broad interdependent waves

### Root instruction surfaces
- `CLAUDE.md`
- `AGENTS.md`

### Nested instruction surfaces
- `src/fl_mcp/AGENTS.md`
- `src/fl_mcp/transactions/AGENTS.md`
- `src/fl_mcp/graph/AGENTS.md`
- `src/fl_mcp/domains/AGENTS.md`
- `providers/AGENTS.md`
- `tests/AGENTS.md`
- `docs/AGENTS.md`
- `helper/AGENTS.md`
- `scripts/AGENTS.md`

## 15. Persistence model

Use SQLite for:
- config overlays where appropriate
- runtime sessions
- snapshot metadata
- project snapshots
- transactions
- transaction operations
- checkpoints
- rollbacks
- provider registry/cache metadata
- diagnostics runs
- artifacts

## 16. CI/CD and repo operations

### Mandatory CI
- lint
- type check
- unit tests
- integration tests
- docs build
- docs/reference drift check
- security checks
- dependency checks
- license checks
- benchmark smoke

### Matrix
- Linux
- macOS
- Windows

### Pre-commit
- Ruff
- Pyright
- pytest fast subset
- prettier
- eslint
- markdownlint
- yamllint
- actionlint
- commitlint
- typos

### Release automation
- trunk-based development
- Conventional Commits
- automated changelog
- prereleases + stable releases
- PyPI
- GitHub Releases
- helper binaries/artifacts
- docs deploy to Vercel
- Docker image publish

## 17. Milestone roadmap

### Phase 0 — bootstrap
- repo skeleton
- workspace
- FastMCP config
- docs shell
- CI shell
- helper shell
- root instruction files
- templates

### Phase 1 — core runtime foundation
- settings/logging/persistence
- FastMCP server shell
- resources/tools/prompts/apps skeleton
- canonical schemas
- transaction envelope models
- graph skeleton
- CLI scaffold

### Phase 2 — FL bridge foundation
- control plane
- FL bundle installer layout
- bridge protocols
- diagnostics/doctor
- helper app shell

### Phase 3 — read model depth
- snapshot extraction
- graph hydration
- top-level resources
- `query_project`
- on-demand refresh

### Phase 4 — transaction engine depth
- planner
- preconditions
- diff generation
- checkpoint metadata
- apply orchestration
- rollback reporting

### Phase 5 — domain completion
- transport
- mixer
- channels/instruments
- patterns
- piano roll
- plugins/parameters
- VFX/Patcher
- audio/render/export

### Phase 6 — providers/SDK/templates
- provider API
- Python SDK
- typed client SDK
- manifest tooling
- external provider template
- first-party providers

### Phase 7 — docs and UI polish
- flagship docs IA complete
- generated references live
- comparison pages
- diagnostics apps
- transaction preview/app UI
- troubleshooting and runbooks

### Phase 8 — release hardening
- compatibility validation
- benchmark tuning
- packaging/publishing
- prereleases
- `0.1.0`

## 18. Definition of done for `0.1.0`
- deep read and mutation coverage across all chosen FL domains
- canonical schemas stabilized for v0.1
- docs/reference complete
- provider SDK/template path validated
- helper app usable
- client guides validated for Claude/Codex/Gemini/Copilot
- CI/release pipelines green
- security/license/dependency gates clean
