"""Unified CLI for FL MCP."""

import typer

from fl_mcp.apps.diagnostics import diagnostics_summary
from fl_mcp.persistence.db import init_db
from fl_mcp.server.http import run_http
from fl_mcp.server.stdio import run_stdio

app = typer.Typer(help="Unified CLI for FL MCP")


@app.command("server")
def server(transport: str = typer.Option("stdio", help="stdio or http")) -> None:
    """Run MCP server in selected transport mode."""
    if transport == "stdio":
        run_stdio()
    elif transport == "http":
        run_http()
    else:
        raise typer.BadParameter("transport must be stdio or http")


@app.command("install")
def install() -> None:
    """Install FL bundle shell assets."""
    typer.echo("Install shell complete: deploy fl-bundle assets (placeholder)")


@app.command("doctor")
def doctor() -> None:
    """Run diagnostics and env checks."""
    init_db()
    typer.echo(str(diagnostics_summary()))


if __name__ == "__main__":
    app()
