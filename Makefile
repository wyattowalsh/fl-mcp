.PHONY: test quality docs

test:
	uv run pytest -q

quality:
	./scripts/quality.sh

docs:
	pnpm --dir docs docs:generate-reference
	pnpm --dir docs build
