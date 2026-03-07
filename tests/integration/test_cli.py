from fl_mcp.cli.main import main


def test_doctor_runs() -> None:
    assert main(["doctor", "--format", "json"]) == 0
