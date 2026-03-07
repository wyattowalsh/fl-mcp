from typer.testing import CliRunner

from fl_mcp.cli.main import app


def test_doctor_runs() -> None:
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
