"""Local loopback control plane scaffolding."""

from pydantic import BaseModel


class BridgeHealth(BaseModel):
    status: str = "ok"
    transport: str = "loopback"


def ping() -> BridgeHealth:
    return BridgeHealth()
