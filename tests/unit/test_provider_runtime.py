from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from fl_mcp.providers.runtime import ProviderRegistry, reset_provider_registry
from fl_mcp.tools.public import manage_providers


@dataclass
class DummyProvider:
    manifest: dict[str, object]
    startup_calls: int = 0
    shutdown_calls: int = 0

    def startup(self) -> None:
        self.startup_calls += 1

    def shutdown(self) -> None:
        self.shutdown_calls += 1

def test_provider_registry_register_startup_shutdown() -> None:
    registry = ProviderRegistry()
    provider = DummyProvider(
        manifest={
            "name": "dummy",
            "version": "0.1.0",
            "capabilities": ["diag"],
            "maturity": "beta",
        }
    )

    manifest = registry.register(provider)
    assert manifest.name == "dummy"
    assert registry.startup_all() == 1
    assert registry.shutdown_all() == 1

    statuses = registry.statuses()
    assert statuses[0]["state"] == "stopped"


def test_provider_registry_load_from_module(tmp_path: Path, monkeypatch) -> None:
    package_dir = tmp_path / "temp_provider"
    package_dir.mkdir(parents=True)
    module_file = package_dir / "__init__.py"
    module_file.write_text(
        """
class TempProvider:
    def __init__(self):
        self.manifest = {
            'name': 'module-provider',
            'version': '1.0.0',
            'capabilities': ['render'],
            'maturity': 'stable',
        }

    def startup(self):
        pass

    def shutdown(self):
        pass

provider = TempProvider()
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    registry = ProviderRegistry()
    manifest = registry.load_from_module("temp_provider")
    assert manifest.name == "module-provider"



def test_manage_providers_default_and_load_module(tmp_path: Path, monkeypatch) -> None:
    package_dir = tmp_path / "temp_provider_load"
    package_dir.mkdir(parents=True)
    module_file = package_dir / "__init__.py"
    module_file.write_text(
        """
class TempProvider:
    def __init__(self):
        self.manifest = {
            'name': 'load-provider',
            'version': '1.1.0',
            'capabilities': ['analyze'],
            'maturity': 'experimental',
        }

    def startup(self):
        pass

    def shutdown(self):
        pass

def create_provider():
    return TempProvider()
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    reset_provider_registry()

    initial = manage_providers()
    assert initial["tool"] == "manage_providers"
    assert initial["status"] == "ok"

    loaded = manage_providers(action="load_module", module="temp_provider_load")
    assert loaded["status"] == "ok"
    providers = loaded["providers"]
    assert isinstance(providers, list)
    assert providers[0]["manifest"]["name"] == "load-provider"

    reset_provider_registry()
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))
