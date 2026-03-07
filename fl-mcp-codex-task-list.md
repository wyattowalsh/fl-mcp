
# FL MCP — Codex Parallel Task List

## 1. Operating model

Use massively parallel subagents, but only where file overlap is low and dependency structure permits clean merges.

### Global rules
- Do not expand the public API casually.
- Keep the public MCP surface small and purpose-driven.
- Maintain one task ledger in-repo.
- Assign one integration/merge marshal.
- Every task must declare:
  - inputs
  - outputs
  - touched paths
  - dependencies
  - done criteria
- Reuse from existing FL MCP repos only after license + architectural fit review.
- Keep patches coherent and reviewable.

## 2. Required persistent coordination artifacts

Create these immediately:
- `BUILD_STATUS.md`
- `docs/content/docs/architecture/public-api-inventory.mdx`
- `docs/content/docs/architecture/reuse-audit.mdx`
- `adr/index.md`

`BUILD_STATUS.md` must track:
- task id
- owner/subagent
- status
- dependencies
- files/paths
- blockers
- merge notes

## 3. Parallel work waves

## Wave 0 — bootstrap

### T00 — root repo scaffold
**Inputs**
- approved repo structure
- naming decisions

**Outputs**
- root tree
- `pyproject.toml`
- `package.json`
- `pnpm-workspace.yaml`
- `fastmcp.json`

**Touched paths**
- root
- `src/`
- `docs/`
- `tests/`
- `providers/`
- `helper/`
- `fl-bundle/`

**Dependencies**
- none

**Done criteria**
- uv installs
- pnpm installs
- base tree exists

---

### T01 — repo metadata and hygiene
**Outputs**
- `README.md`
- `LICENSE`
- `CHANGELOG.md`
- `.editorconfig`
- `.gitignore`
- `.gitattributes`
- `.python-version`

**Done**
- all names consistent with `fl-mcp`

---

### T02 — AI instruction system
**Outputs**
- root `CLAUDE.md`
- root `AGENTS.md`
- nested `AGENTS.md`
- `.claude/agents/*`
- `.claude/commands/*`
- `.claude/hooks/*`
- `.claude/output-styles/*`
- `.claude/playbooks/*`
- `.claude/templates/*`

**Done**
- instructions align with architecture invariants
- no contradictions

---

### T03 — GitHub templates and governance
**Outputs**
- issue templates
- PR templates
- ADR template
- design proposal template
- `CODEOWNERS`

**Done**
- all templates render and are useful

---

### T04 — pre-commit and local quality tooling
**Outputs**
- `.pre-commit-config.yaml`
- lint/type/test configs

**Done**
- pre-commit runs cleanly on scaffold

## Wave 1 — runtime foundation

### T10 — FastMCP server bootstrap
**Outputs**
- stdio entrypoint
- streamable HTTP entrypoint
- server shell
- health surface

**Paths**
- `src/fl_mcp/server/`
- `src/fl_mcp/runtime/`

**Done**
- server starts in both modes

---

### T11 — config/settings system
**Outputs**
- Pydantic Settings config model
- root config + env + local override support

**Paths**
- `src/fl_mcp/config/`

**Done**
- config loads deterministically in tests and runtime

---

### T12 — logging and diagnostics base
**Outputs**
- Loguru setup
- structured JSON logs
- rich local console output
- request/transaction correlation ids

**Paths**
- `src/fl_mcp/logging/`
- `src/fl_mcp/middleware/`

**Done**
- logs are structured and testable

---

### T13 — auth, transforms, middleware skeleton
**Outputs**
- local optional token auth
- transform pipeline shell
- safety gating middleware
- exception normalization middleware

**Paths**
- `src/fl_mcp/auth/`
- `src/fl_mcp/transforms/`
- `src/fl_mcp/middleware/`

**Done**
- auth configurable
- middleware registered

---

### T14 — prompts and apps shell
**Outputs**
- prompt registry
- diagnostics app shell
- transaction preview/apply UI shell
- runtime inspector UI shell

**Paths**
- `src/fl_mcp/prompts/`
- `src/fl_mcp/apps/`

**Done**
- at least one prompt and one app load successfully

## Wave 2 — schemas, graph, transactions

### T20 — canonical schemas
**Outputs**
- transaction envelope
- result models
- snapshot models
- provider manifest models
- schema versioning policy

**Paths**
- `src/fl_mcp/schemas/`

**Done**
- JSON Schema generation works

---

### T21 — canonical project graph
**Outputs**
- graph node/edge types
- snapshot model
- serialization
- projection conventions

**Paths**
- `src/fl_mcp/graph/`

**Done**
- graph state round-trips reliably

---

### T22 — planner/compiler
**Outputs**
- intent -> typed operations compilation
- preconditions
- diff model
- plan validation

**Paths**
- `src/fl_mcp/transactions/`

**Done**
- planner unit tests pass

---

### T23 — apply engine and rollback classification
**Outputs**
- apply orchestrator
- partial/all-or-nothing policy
- rollback capability model
- post-apply verification hooks

**Paths**
- `src/fl_mcp/transactions/`

**Done**
- transaction result model stable and tested

---

### T24 — persistence layer
**Outputs**
- SQLModel models
- Alembic migrations
- checkpoint/audit persistence
- snapshot persistence metadata

**Paths**
- `src/fl_mcp/persistence/`

**Done**
- migrations apply and rollback cleanly

## Wave 3 — public MCP contract

### T30 — resources-first read surface
**Outputs**
- project resources
- runtime resources
- transaction/checkpoint resources
- provider/schema resources

**Paths**
- `src/fl_mcp/resources/`

**Done**
- resources typed and documented

---

### T31 — `query_project`
**Outputs**
- semantic query tool over graph/resources
- minimal but powerful query surface

**Done**
- does not inflate public tool count

---

### T32 — `plan_changes`
**Outputs**
- previewable transaction planning
- typed domain payload intake
- diff output

**Done**
- returns checkpoint strategy + warnings

---

### T33 — `apply_changes`
**Outputs**
- transaction execution
- safety policy handling
- checkpointing
- partial/all-or-nothing support

**Done**
- robust result contract in place

---

### T34 — runtime/render/provider tools
**Outputs**
- `render_project`
- `analyze_audio`
- `inspect_runtime`
- `manage_providers`

**Done**
- all tools documented and typed

## Wave 4 — FL bridge and bundle

### T40 — local control plane
**Outputs**
- loopback control protocol
- async orchestration layer
- sync-friendly facades

**Paths**
- `src/fl_mcp/bridge/`

**Done**
- bridge protocol tested locally

---

### T41 — FL bundle scaffold
**Outputs**
- controller scripts scaffold
- piano-roll scripts scaffold
- VFX scripts scaffold
- shared bundle assets

**Paths**
- `fl-bundle/`

**Done**
- bundle structure installable

---

### T42 — installer and doctor
**Outputs**
- `fl-mcp install`
- `fl-mcp doctor`
- config validation
- environment validation
- FL bundle deployment flow

**Done**
- diagnostics produce actionable output

---

### T43 — runtime diagnostics model
**Outputs**
- bridge health
- bundle health
- config health
- runtime health resource

**Done**
- diagnostics surfaced in CLI and resources

## Wave 5 — domain implementation teams

All domain teams must honor:
- canonical graph contracts
- transaction contracts
- resource conventions
- public API constraints

### T50 — transport domain
### T51 — mixer domain
### T52 — channels/instruments domain
### T53 — patterns/playlist domain
### T54 — piano roll domain
### T55 — plugins/parameters domain
### T56 — VFX/Patcher domain
### T57 — audio/render domain

**For each domain, outputs**
- graph models
- read resource projections
- planner/compiler hooks
- mutation handlers
- docs stubs
- tests

**Done criteria**
- deep read + mutation support
- transaction classification on all mutations
- docs/reference generated

## Wave 6 — providers and SDKs

### T60 — provider runtime core
**Outputs**
- in-process provider loading
- registration/discovery
- compatibility declarations
- provider lifecycle hooks

**Done**
- providers load and validate cleanly

---

### T61 — Python provider SDK
**Outputs**
- provider base classes
- transaction/resource helpers
- manifest helpers
- test helpers

**Done**
- external provider template can build against SDK

---

### T62 — typed client SDK
**Outputs**
- resource readers
- plan/apply helpers
- runtime client helpers

**Done**
- examples run

---

### T63 — external provider template
**Outputs**
- template package
- manifest example
- tests
- docs

**Done**
- template validates and installs

---

### T64 — first-party providers
**Outputs**
- style-memory provider shell
- audio-analysis provider shell
- export-tools provider shell

**Done**
- all register successfully and are documented

## Wave 7 — docs and helper

### T70 — docs scaffold and branding
**Outputs**
- Fumadocs shell
- custom navigation
- theme
- homepage
- architecture landing

**Done**
- docs app runs locally

---

### T71 — generated reference pipeline
**Outputs**
- schema docs
- resource/tool catalog
- provider manifest docs
- compatibility/reference pages

**Done**
- deterministic generation in CI

---

### T72 — flagship content
**Outputs**
- getting started
- install
- concepts
- architecture
- ADR index
- providers
- clients
- helper docs
- troubleshooting
- security
- release notes
- roadmap
- contributing
- AI workflows
- comparison page vs existing FL Studio MCP servers

**Done**
- flagship IA complete

---

### T73 — helper app shell
**Outputs**
- Swift/SwiftUI menu bar app
- status panel
- logs panel
- quick actions

**Done**
- app launches and displays runtime status

---

### T74 — helper/setup integration
**Outputs**
- helper-guided install
- helper-guided diagnostics
- helper + CLI coordination

**Done**
- helper and runtime integrate cleanly

## Wave 8 — testing, release, hardening

### T80 — tests completion
**Outputs**
- unit
- integration
- contract
- e2e skeletons
- benchmark smoke

**Done**
- all suites runnable in CI

---

### T81 — CI/CD completion
**Outputs**
- Linux/macOS/Windows workflows
- prerelease/release pipelines
- docs deploy
- Docker publish
- PyPI publish

**Done**
- workflows green

---

### T82 — security/license/dependency automation
**Outputs**
- vulnerability checks
- license checks
- dependency freshness
- reuse audit hooks

**Done**
- release gates enforce policy

---

### T83 — release readiness
**Outputs**
- release checklist
- docs version
- changelog
- sample configs
- migration notes
- `0.1.0` RC package

**Done**
- release candidate is publishable

## 4. Integration Marshal task

### T90 — integration marshal
Assign one subagent as overall integration marshal.

**Responsibilities**
- maintain `BUILD_STATUS.md`
- manage dependencies
- prevent path collisions
- enforce naming consistency
- maintain ADR index
- maintain public API inventory
- reject accidental API expansion
- coordinate rebases/merges
- maintain reuse audit
- verify docs/code/schema consistency

**Done**
- no major merge chaos
- architecture remains coherent

## 5. Suggested initial subagent allocation

Start with:
1. bootstrap/config
2. AI ergonomics and instruction files
3. server/runtime shell
4. schemas/graph
5. transactions/persistence
6. docs scaffold
7. FL bundle/installer
8. CI/CD + templates
9. integration marshal

Then fan out domain teams after schema and transaction contracts stabilize.

## 6. Priority order for execution

### Must stabilize first
- repo scaffold
- root instruction files
- server shell
- config/logging
- canonical schemas
- project graph skeleton
- transaction envelope
- task ledger
- CI shell

### Then parallelize aggressively
- resources
- tools
- persistence
- FL bundle
- diagnostics
- docs scaffold
- domain teams
- provider SDK
- helper app

### Then harden and release
- generated reference
- examples
- comparison docs
- compatibility guides
- release automation
- benchmark and security gates

## 7. Hard stop checks before `0.1.0`
- public API still small and coherent
- every domain has deep read + mutation support
- provider API stable and documented
- docs/reference synced
- helper app usable
- clients validated
- release pipelines green
- security/license/dependency checks passing
