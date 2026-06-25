---
name: fl-mcp-production-flow
description: >-
  Create setup-gated FL MCP production workflows for FL Studio: setup, mock
  rehearsal, live execution, render, and audio evidence. Use when producing or
  verifying projects through fl-mcp. NOT for server code, public MCP tools, DB,
  pipelines, UI, or tutorials.
argument-hint: "<mode> [workflow]"
model: opus
license: MIT
compatibility: "Requires Python 3.12+ and uv/uvx for setup checks. Live FL Studio mode requires the FL MCP bridge and FL Studio controller script."
metadata:
  author: wyattowalsh
  version: "1.0.0"
---

# FL MCP Production Flow

Guide safe FL Studio production workflows through FL MCP's compact FastMCP
surface. Every workflow starts with setup verification, then uses the compact
loop: orient, search capabilities, fetch schema, execute or plan/apply, verify.

## Canonical Vocabulary

Canonical terms (use these exactly):

| Term | Meaning |
| --- | --- |
| **Setup Gate** | Mandatory preflight before every non-setup mode |
| **mock rehearsal** | Deterministic `provider="mock"` workflow used before live attempts |
| **live attempt** | Any operation that can touch actual FL Studio state |
| **compact loop** | Orient -> search capabilities -> fetch schema -> execute/plan/apply -> verify |
| **evidence bundle** | Setup JSON plus provider, bridge, operation, request, task, and readback proof |
| **degraded setup** | Setup check is blocked but Plan mode may continue with exact missing steps |

## Gallery

Invoke the skill with **no arguments** (`/fl-mcp-production-flow`) to show this
gallery. Every example starts with setup; none begin live mutation without an
explicit workflow.

| Example | Mode | Safe entry command |
| --- | --- | --- |
| First-time readiness | Setup | `/fl-mcp-production-flow setup mock` |
| Live bridge readiness | Setup | `/fl-mcp-production-flow setup live` |
| Sketch a beat workflow | Plan | `/fl-mcp-production-flow plan "four-bar hardstyle loop"` |
| Mock rehearsal before live | Rehearse | `/fl-mcp-production-flow rehearse transport-tempo-mock` |
| Live transport change | Execute | `/fl-mcp-production-flow execute transport-set-tempo-live` |
| Export with task evidence | Render | `/fl-mcp-production-flow render master-wav` |
| Inspect prior proof | Audit | `/fl-mcp-production-flow audit render result` |

Gallery rules:

1. Recommend **Setup** first for empty invocations.
2. Default new production requests to **Plan** or **Rehearse** unless live
   intent is explicit.
3. Never claim DAW mutation from mock evidence.
4. Redirect runtime/API, database, pipeline, and UI requests out of this skill.

## Dispatch

| `$ARGUMENTS` | Mode | Action |
| --- | --- | --- |
| `setup [mock|live|source|published]` | Setup | Verify FL MCP installation, CLI, client setup, and optional live bridge readiness |
| `plan <goal>` | Plan | Create a production workflow plan without mutation |
| `rehearse <workflow>` | Rehearse | Use mock-mode rehearsal before live work |
| `execute <workflow>` | Execute | Execute only after Setup Gate and live/mock intent are clear |
| `render <target>` | Render | Render/export workflow with task evidence |
| `audit <state|result>` | Audit | Inspect setup, readback, render, or audio-analysis evidence |
| Natural-language production request | Auto | Run Setup Gate, then route to Plan, Rehearse, or Execute |
| Empty | Gallery | Show setup-first examples and safe entry points |

### Auto-Detection

1. Requests about installing, connecting, MCP client setup, bridge readiness, or
   "is this ready?" -> **Setup**.
2. Requests to sketch, design, sequence, or decide a production workflow ->
   **Plan**.
3. Requests mentioning mock, dry run, rehearsal, or safety check ->
   **Rehearse**.
4. Requests to perform FL Studio actions -> **Execute** only after Setup Gate.
5. Requests to export, bounce, render, or analyze audio -> **Render**.
6. Requests to inspect proof, logs, readback, task state, or results -> **Audit**.
7. Requests to change server/runtime code, public MCP tools, schemas, DB,
   pipeline, or UI surfaces -> redirect to the appropriate engineering skill.

## Classification/Gating Logic

| Signal | Route | Execution Allowed |
| --- | --- | --- |
| setup, install, MCP client, bridge, doctor | Setup | No DAW mutation |
| plan, sequence, design a beat, decide workflow | Plan | No DAW mutation |
| mock, dry run, rehearse, safe example | Rehearse | Mock only |
| live, actual FL Studio, change project, mutate | Execute | Only after live Setup Gate and explicit live intent |
| render, export, bounce, analyze audio | Render | Mock or live based on Setup Gate and intent |
| inspect proof, readback, task, status, result | Audit | Read-only |
| server code, public MCP tools, DB, pipeline, UI | Redirect | Not in this skill |

## Mandatory Setup Gate

Run before every mode except explicit `setup`.

1. Run:

   ```bash
   python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode mock --source auto --repo-root . --format json
   ```

2. If the workflow needs live FL Studio, also run:

   ```bash
   python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode live --source auto --repo-root . --format json
   ```

3. Parse JSON output:
   - `safe_to_execute_mock: true` is required for Rehearse.
   - `safe_to_attempt_live: true` plus explicit user live intent is required
     before live Execute or Render attempts.
   - Plan may continue in degraded setup status, but must list
     `missing_steps` exactly.
4. Never claim actual DAW state changed unless FL MCP tool results show live
   provider/bridge evidence and readback or task evidence.

Load `references/setup.md` when Setup Gate fails or the user asks about setup.

## Progressive Disclosure

Start with this file for routing and non-negotiable rules. Load only the next
needed reference:

1. `references/setup.md` for setup checks, failures, and remediation.
2. `references/compact-loop.md` before planning unfamiliar operations.
3. `references/production-recipes.md` for workflow-specific sequencing.
4. `references/live-mode-safety.md` before any live attempt.
5. `references/validation.md` when auditing or reporting evidence.

## Mode: Setup

Use Setup mode to prove the local FL MCP environment is ready.

1. Classify target as mock, live, source checkout, or published package.
2. Run `scripts/setup-check.py` with the matching `--mode` and `--source`.
3. Report status, missing steps, safe execution flags, and client config.
4. For live mode, include bridge setup and controller-script readiness without
   mutating FL Studio.
5. Do not proceed to production actions until the required safe flag is true.

## Mode: Plan

Create an execution plan without mutation.

1. Run the Setup Gate.
2. Orient with the intended read path: `fl_status`, `fl_snapshot`, or resources.
3. Identify likely domains and operation searches.
4. Specify schema lookups before every operation.
5. Define readback or task verification for each action.
6. State whether the workflow should start in mock, live, or both.

## Mode: Rehearse

Use deterministic mock mode before live work.

1. Require `safe_to_execute_mock: true`.
2. Use `fl_search_capabilities` to find operations.
3. Use `fl_get_capability_schema` for exact payloads and provider notes.
4. Execute safe representative operations with explicit `provider="mock"`.
5. Verify with readback, follow-up snapshot, task state, or audio-analysis state.

## Mode: Execute

Execute FL MCP actions only inside the compact surface.

1. Run Setup Gate and confirm mock or live target.
2. For live DAW mutation, ask for explicit live intent if it is not already
   present in the user request.
3. Search capability and fetch schema before every operation.
4. Prefer `fl_plan` and `fl_apply` when rollback or multi-step mutation matters.
5. Capture operation id, request id, provider, bridge mode, result, and readback.
6. If setup or provider evidence is insufficient, stop and return missing steps.

## Mode: Render

Render/export and analyze audio with task evidence.

1. Run Setup Gate for mock or live mode.
2. Use `fl_render` for render/export tasks.
3. Record task id, provider, bridge mode, output path, and status.
4. Use `fl_analyze_audio` when audio quality or exported artifact evidence is
   needed.
5. Verify through task resources or follow-up status; do not infer completion
   from task creation alone.

## Mode: Audit

Inspect evidence without changing project state.

1. Read setup JSON, FL MCP tool results, task ids, readback, or snapshots.
2. Separate mock evidence from live evidence.
3. Flag missing provider, bridge mode, operation id, request id, task id, or
   readback.
4. Recommend the narrowest next setup or workflow step.

## Scope Boundaries

This skill is for operating FL MCP production workflows. It is not for:

- server/runtime implementation or public MCP tool changes;
- database schema design or migrations; use `database-architect`;
- ingestion, transformation, lineage, or data contracts; use
  `data-pipeline-architect`;
- visual docs/app UI work; use frontend/UI skills;
- generic FL Studio tutorials outside the FL MCP surface.

## Reference File Index

Load one reference at a time.

| File | Content | Read When |
| --- | --- | --- |
| `references/setup.md` | Setup mode, setup-check JSON, degraded states, remediation commands | Setup Gate, setup failures |
| `references/compact-loop.md` | Compact FastMCP loop and public-surface boundaries | Planning or executing workflows |
| `references/production-recipes.md` | Common production, arrangement, plugin, render, and audit recipes | Plan, Rehearse, Execute, Render |
| `references/live-mode-safety.md` | Live bridge safety, confirmation rules, scratch-project safeguards | Live Execute or Render |
| `references/validation.md` | Evidence checklist and validation report shape | Audit and final reporting |

## Validation Contract

Before declaring this skill complete after edits, run:

```bash
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode mock --source local --repo-root . --format json
python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode live --source local --repo-root . --format json
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile skills/fl-mcp-production-flow/scripts/setup-check.py
python3 -m json.tool skills/fl-mcp-production-flow/evals/evals.json >/dev/null
python3 <skill-creator>/scripts/audit.py skills/fl-mcp-production-flow/
npx skills add . --skill fl-mcp-production-flow --list
```

For centralized harness reconciliation, run `WAGENTS_REPO_ROOT=<agents-repo>
wagents validate` and `WAGENTS_REPO_ROOT=<agents-repo> wagents eval validate`
from the configured agents repository. Do not run centralized `wagents
validate` from this checkout unless it has been wired as a wagents repository.

Completion criteria:

- setup checks return actionable JSON;
- eval validation passes;
- audit grade is A (90+);
- install discovery lists `fl-mcp-production-flow`;
- docs and public-surface checks pass when repo docs changed.

## Critical Rules

1. Never bypass setup for Rehearse, Execute, Render, or Audit.
2. Never call primitive FL operations as visible MCP tools.
3. Always use capability search and schema lookup before execution.
4. Default to mock rehearsal unless live intent is explicit.
5. Never mutate live FL Studio without explicit user/live intent.
6. Never claim live success from mock evidence.
7. Capture provider, bridge mode, task id, operation id, request id, and
   readback evidence when relevant.
8. Stop on missing setup for execution modes; return exact missing steps.
9. Keep public MCP surface unchanged; route runtime/API changes away.
10. Route DB, data-pipeline, and UI work to the appropriate skills.
