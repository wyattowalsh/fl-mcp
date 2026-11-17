test:
    uv run pytest -q

precommit:
    uv run pre-commit run --all-files --show-diff-on-failure

lint:
    uv run pre-commit run --all-files --show-diff-on-failure

typecheck:
    uv run ty check src/

audit:
    uv run --with pip-audit==2.10.0 pip-audit

quality: lint typecheck audit

docs:
    pnpm --dir docs --ignore-workspace docs:generate-reference
    pnpm --dir docs --ignore-workspace lint
    pnpm --dir docs --ignore-workspace check
    pnpm --dir docs --ignore-workspace build

package:
    uv build
    uv run --with twine==6.2.0 twine check dist/*

ci: quality test docs package

verify:
    uv run pytest tests/contract/test_public_surface.py -q
    uv run fl-mcp doctor --format json
    pnpm --dir docs --ignore-workspace check
    python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode mock --source local --repo-root . --format json
    python3 skills/fl-mcp-production-flow/scripts/setup-check.py --mode live --source local --repo-root . --format json
