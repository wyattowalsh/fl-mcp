"""Install command handlers."""

from __future__ import annotations

import argparse
import json


def build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    install_parser = subparsers.add_parser("install", help="Install dependencies and local assets")
    install_parser.add_argument(
        "--target",
        default="local",
        choices=("local", "system"),
        help="Installation target",
    )
    install_parser.add_argument(
        "--dry-run", action="store_true", help="Print install plan without executing"
    )
    install_parser.set_defaults(handler=handle_install)


def handle_install(args: argparse.Namespace) -> int:
    payload = {
        "action": "install",
        "target": args.target,
        "dry_run": args.dry_run,
        "status": "scaffold-ready",
    }
    print(json.dumps(payload, indent=2))
    return 0
