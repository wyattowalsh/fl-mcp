"""Streamable HTTP transport entrypoint."""

from fl_mcp.config.settings import settings
from fl_mcp.server.app import create_server


def run_http() -> None:
    server = create_server()
    print(f"{server.name} http-stream ready on {settings.http_host}:{settings.http_port}")


if __name__ == "__main__":
    run_http()
