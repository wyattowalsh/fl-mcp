"""In-process provider runtime core."""

from typing import Protocol

from fl_mcp.schemas import ProviderManifest


class Provider(Protocol):
    manifest: ProviderManifest

    def startup(self) -> None: ...

    def shutdown(self) -> None: ...


class ProviderRegistry:
    """Provider registry and lifecycle manager."""

    def __init__(self) -> None:
        self._providers: list[Provider] = []

    def register(self, provider: Provider) -> None:
        self._providers.append(provider)

    def manifests(self) -> list[ProviderManifest]:
        return [p.manifest for p in self._providers]
