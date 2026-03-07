"""Minimal sqlmodel shim."""

class _Meta:
    def create_all(self, engine):
        return None


class SQLModel:
    metadata = _Meta()


class Field:
    def __init__(self, default=None, primary_key=False):
        self.default = default
        self.primary_key = primary_key


def create_engine(url: str, echo: bool = False):
    return {"url": url, "echo": echo}
