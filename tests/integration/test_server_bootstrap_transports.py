import pytest

from fl_mcp.server.bootstrap import bootstrap_server


@pytest.mark.parametrize(
    ("transport", "expected"),
    [
        ("stdio", "stdio"),
        ("streamable-http", "streamable-http"),
        ("streamable_http", "streamable-http"),
    ],
)
def test_server_bootstraps_supported_transports(transport: str, expected: str) -> None:
    runtime = bootstrap_server(transport)

    assert runtime.transport == expected
    assert runtime.started is True
