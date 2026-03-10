"""Template provider package."""

from __future__ import annotations

from typing import Any


class TemplateProvider:
    """Minimal provider implementation used by template packaging."""

    def __init__(self) -> None:
        self.manifest: dict[str, Any] = {
            "name": "template-provider",
            "version": "0.1.0",
            "capabilities": ["template"],
            "maturity": "experimental",
            "entrypoint": "template_provider:provider",
            "description": "Example provider template.",
        }

    def startup(self) -> None:
        """No-op startup hook for template provider."""

    def shutdown(self) -> None:
        """No-op shutdown hook for template provider."""


provider = TemplateProvider()


def create_provider() -> TemplateProvider:
    """Factory export for module loading flows."""
    return TemplateProvider()


__all__ = ["TemplateProvider", "create_provider", "provider"]
