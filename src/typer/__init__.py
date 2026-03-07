"""Minimal typer shim."""

from __future__ import annotations

from typing import Callable


class BadParameter(ValueError):
    pass


def Option(default, **kwargs):
    return default


def echo(message: str) -> None:
    print(message)


class Typer:
    def __init__(self, help: str | None = None) -> None:
        self._commands: dict[str, Callable[..., None]] = {}

    def command(self, name: str):
        def decorator(func: Callable[..., None]) -> Callable[..., None]:
            self._commands[name] = func
            return func

        return decorator

    def __call__(self) -> None:
        return None
