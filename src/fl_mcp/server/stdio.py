"""stdio transport entrypoint."""

from fl_mcp.server.app import create_server


def run_stdio() -> None:
    server = create_server()
    print(f"{server.name} stdio transport ready")


if __name__ == "__main__":
    run_stdio()
