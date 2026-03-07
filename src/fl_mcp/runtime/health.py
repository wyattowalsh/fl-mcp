"""Runtime health models."""

from pydantic import BaseModel


class RuntimeHealth(BaseModel):
    """Health state for server runtime."""

    status: str = "ok"
    version: str = "0.1.0a0"
    details: dict[str, str] = {"mode": "local-only"}
