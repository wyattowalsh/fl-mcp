"""CLI package for FL MCP tools."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Lazy entrypoint wrapper to avoid import cycles in module execution."""

    from .main import main as _main

    return _main(argv)


__all__ = ["main"]
