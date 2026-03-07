#!/usr/bin/env bash
set -euo pipefail

uv run pytest -q
uvx pre-commit run --all-files --show-diff-on-failure
