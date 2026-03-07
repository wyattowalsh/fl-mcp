import pytest

from fl_mcp.server.bootstrap import bootstrap_server


@pytest.mark.parametrize("transport", ["stdio", "streamable_http"])
def test_server_bootstraps_supported_transports(transport: str) -> None:
    runtime = bootstrap_server(transport)

    assert runtime.transport == transport
    assert runtime.started is True
