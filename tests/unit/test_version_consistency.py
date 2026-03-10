from fl_mcp import __version__
from fl_mcp.config import RuntimeConfig
from fl_mcp.runtime.health import RuntimeHealth


def test_runtime_config_and_health_defaults_use_package_version() -> None:
    assert RuntimeConfig().service_version == __version__
    assert RuntimeHealth().version == __version__
