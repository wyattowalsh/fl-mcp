"""Settings models."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for FL MCP.

    Parameters
    ----------
    app_name:
        Human-readable runtime name.
    log_level:
        Default log level for local console output.
    auth_token:
        Optional local token for guarded execution.
    http_host:
        Host bound by streamable HTTP transport.
    http_port:
        Port bound by streamable HTTP transport.
    """

    model_config = SettingsConfigDict(
        env_prefix="FL_MCP_",
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = "fl-mcp"
    log_level: str = "INFO"
    auth_token: str | None = None
    http_host: str = "127.0.0.1"
    http_port: int = Field(default=8765, ge=1, le=65535)
    database_url: str = "sqlite:///fl_mcp.db"


settings = Settings()
