"""Minimal pydantic-settings shim."""

from pydantic import BaseModel


class SettingsConfigDict(dict):
    pass


class BaseSettings(BaseModel):
    pass
