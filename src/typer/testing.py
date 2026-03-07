"""Minimal typer.testing shim."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Result:
    exit_code: int
    stdout: str


class CliRunner:
    def invoke(self, app, args):
        try:
            if not args:
                return Result(0, "")
            cmd = args[0]
            func = app._commands[cmd]
            if cmd == "server" and len(args) > 1:
                func(args[1])
            else:
                func()
            return Result(0, "")
        except Exception as exc:  # pragma: no cover
            return Result(1, str(exc))
