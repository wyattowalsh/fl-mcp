#!/usr/bin/env bash
set -euo pipefail

uv run pytest -q
uv run pre-commit run --all-files --show-diff-on-failure
uv run --with pip-audit==2.10.0 pip-audit
