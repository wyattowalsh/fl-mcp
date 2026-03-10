from __future__ import annotations

import importlib
import tomllib
from dataclasses import dataclass
from importlib import metadata
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


def test_provider_registry_discover_entry_points_is_resilient(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_dir = tmp_path / "temp_provider_ep"
    package_dir.mkdir(parents=True)
    module_file = package_dir / "__init__.py"
    module_file.write_text(
        """
class TempProvider:
    def __init__(self):
        self.manifest = {
            'name': 'entrypoint-provider',
            'version': '2.0.0',
            'capabilities': ['diag'],
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
    monkeypatch.setattr(
        "fl_mcp.providers.runtime._entry_points_for_group",
        lambda group: [
            metadata.EntryPoint(
                name="healthy",
                value="temp_provider_ep:provider",
                group=group,
            ),
            metadata.EntryPoint(
                name="broken",
                value="missing_provider_module:provider",
                group=group,
            ),
        ],
    )

    registry = ProviderRegistry()
    discovery = registry.load_from_entry_points()

    assert [manifest.name for manifest in discovery.loaded] == ["entrypoint-provider"]
    assert len(discovery.errors) == 1
    assert discovery.errors[0].entry_point == "broken"
    assert discovery.errors[0].error_type == "ModuleNotFoundError"

    cached = registry.load_from_entry_points()
    assert len(cached.loaded) == 1
    assert len(cached.errors) == 1


def test_manage_providers_discover_surfaces_partial_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_dir = tmp_path / "temp_provider_discover"
    package_dir.mkdir(parents=True)
    module_file = package_dir / "__init__.py"
    module_file.write_text(
        """
class TempProvider:
    def __init__(self):
        self.manifest = {
            'name': 'discover-provider',
            'version': '1.2.3',
            'capabilities': ['render'],
            'maturity': 'experimental',
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
    monkeypatch.setattr(
        "fl_mcp.providers.runtime._entry_points_for_group",
        lambda group: [
            metadata.EntryPoint(
                name="healthy-discover",
                value="temp_provider_discover:provider",
                group=group,
            ),
            metadata.EntryPoint(
                name="broken-discover",
                value="missing_discover_provider:provider",
                group=group,
            ),
        ],
    )
    reset_provider_registry()

    discovery = manage_providers(action="discover")
    assert discovery["status"] == "partial"
    assert discovery["loaded_count"] == 1
    assert discovery["error_count"] == 1
    assert discovery["loaded"][0]["name"] == "discover-provider"
    assert discovery["errors"][0]["entry_point"] == "broken-discover"
    assert discovery["errors"][0]["error_type"] == "ModuleNotFoundError"
    assert discovery["providers"][0]["manifest"]["name"] == "discover-provider"

    reset_provider_registry()


def test_template_provider_module_exports_resolvable_entrypoint(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    template_src = repo_root / "providers" / "template_provider" / "src"
    template_pyproject = repo_root / "providers" / "template_provider" / "pyproject.toml"
    monkeypatch.syspath_prepend(str(template_src))

    pyproject_data = tomllib.loads(template_pyproject.read_text(encoding="utf-8"))
    entry_points = pyproject_data["project"]["entry-points"]["fl_mcp.providers"]
    for target in entry_points.values():
        module_name, export_name = target.split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        exported = getattr(module, export_name, None)
        assert exported is not None

    module = importlib.import_module("template_provider")
    assert module.provider.manifest["entrypoint"] == "template_provider:provider"
    assert module.create_provider().manifest["name"] == "template-provider"


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
