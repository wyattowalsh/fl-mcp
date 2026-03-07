"""Provider manifest schemas."""

from pydantic import BaseModel


class ProviderManifest(BaseModel):
    """Provider registration model."""

    name: str
    version: str
    capabilities: list[str]
    maturity: str = "experimental"
