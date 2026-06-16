import pytest

import fl_mcp.server.app as app_module
from fl_mcp.config import RuntimeConfig


def test_server_app_create_server_delegates_to_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_create_server(runtime_config: object) -> object:
        captured["runtime_config"] = runtime_config
        return sentinel

    monkeypatch.setattr(app_module, "_factory_create_server", fake_create_server)
    result = app_module.create_server(name="shim-service")

    assert result is sentinel
    runtime_config = captured["runtime_config"]
    assert isinstance(runtime_config, RuntimeConfig)
    assert runtime_config.service_name == "shim-service"
