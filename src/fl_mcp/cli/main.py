"""Entry point for FL MCP CLI scaffold."""

from __future__ import annotations

import argparse

from . import config, diagnostics, doctor, install, server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fl-mcp", description="FL MCP command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server.build_parser(subparsers)
    install.build_parser(subparsers)
    doctor.build_parser(subparsers)
    config.build_parser(subparsers)
    diagnostics.build_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return int(handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
