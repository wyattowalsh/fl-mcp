"""Entry point for FL MCP CLI scaffold."""

from __future__ import annotations

import argparse

from fl_mcp import __version__

from . import config, diagnostics, doctor, install, server, template


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all CLI subcommands."""
    parser = argparse.ArgumentParser(prog="fl-mcp", description="FL MCP command line interface")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server.build_parser(subparsers)
    install.build_parser(subparsers)
    doctor.build_parser(subparsers)
    config.build_parser(subparsers)
    diagnostics.build_parser(subparsers)
    template.build_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the FL MCP CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv when None.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return int(handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
