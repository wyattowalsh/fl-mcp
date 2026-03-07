"""Optional local token auth."""

from fl_mcp.config.settings import settings


def check_token(token: str | None) -> bool:
    configured = settings.auth_token
    if configured is None:
        return True
    return token == configured
