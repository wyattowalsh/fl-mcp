# Backlog Manifest

This manifest is the canonical execution index for the `codex/backlog-program` implementation wave stack.

## Scope Sources

- Audit defects and verification regressions captured in session evidence.
- Placeholder/scaffold inventory across `src/`, `helper/`, `fl-bundle/`, and docs.
- Deferred roadmap risks recorded in `BUILD_STATUS.md` (`/research` gate notes).

## Wave Streams

- `T99`: Program bootstrap and wave orchestration ledger.
- `T100`: Core correctness remediation (transactions, graph, auth, fallback compatibility).
- `T101`: Governance and quality hardening (ruff, quality script, CODEOWNERS, workflow permissions).
- `T102`: Docs determinism and lockfile enforcement.
- `T103`: Live FL Studio integration lane (bridge adapters + transaction execution taxonomy).
- `T104`: Provider SDK and runtime lifecycle lane.
- `T105`: Helper productionization lane (real CLI execution + typed payload decoding).
- `T106`: Release deployment lane (PyPI/TestPyPI + docs deploy workflow).
- `T107`: High-conflict integration and contract alignment.
- `T108`: Full verification + post-merge challenge gates.

## Accounting Rule

Each wave follows `N dispatched = N resolved` with bounded recovery:

1. Resume once when recoverable.
2. Re-dispatch once with failure context.
3. Escalate if still unresolved.

## Branch and Isolation Policy

- Marshal branch: `codex/backlog-program`
- Per-stream worktrees (or equivalent isolated worker branches):
  - `codex/w1-core-correctness`
  - `codex/w1-governance-quality`
  - `codex/w1-docs-determinism`
  - `codex/w2-domain-integration`
  - `codex/w2-provider-sdk`
  - `codex/w3-helper-productionization`
  - `codex/w3-release-deployment`

