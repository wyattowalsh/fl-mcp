from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import cast

import pytest

from fl_mcp.providers.builtin import builtin_providers
from fl_mcp.providers.runtime import (
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
)
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS, PROVIDER_MATRIX
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


def test_provider_registry_load_from_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch: pytest.MonkeyPatch,
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


def test_manage_providers_discover_is_disabled_on_public_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_provider_registry()
    registry = get_provider_registry(load_entry_points=False)
    monkeypatch.setattr(
        registry,
        "load_from_entry_points",
        lambda group: pytest.fail("public manage_providers should not discover providers"),
    )

    discovery = manage_providers(action="discover")
    providers = cast(list[dict[str, object]], discovery["providers"])
    assert discovery["status"] == "error"
    assert discovery["action"] == "discover"
    assert discovery["error"] == "action=discover is disabled on the public MCP surface"
    assert discovery["loaded_count"] == 0
    assert discovery["error_count"] == 0
    assert discovery["loaded"] == []
    assert discovery["errors"] == []
    assert len(providers) == len(PROVIDER_MATRIX)


def test_template_provider_fixture_is_not_required_on_public_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    template_src = repo_root / "providers" / "template_provider" / "src"
    template_pyproject = repo_root / "providers" / "template_provider" / "pyproject.toml"

    assert not template_src.exists()
    assert not template_pyproject.exists()
    assert "template-provider" not in PROVIDER_MATRIX


def test_manage_providers_default_and_disabled_load_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_provider_registry()
    registry = get_provider_registry(load_entry_points=False)
    monkeypatch.setattr(
        registry,
        "load_from_module",
        lambda module_path: pytest.fail("public manage_providers should not load modules"),
    )

    initial = manage_providers()
    initial_providers = cast(list[dict[str, object]], initial["providers"])
    assert initial["tool"] == "manage_providers"
    assert initial["status"] == "ok"
    assert {
        cast(dict[str, object], provider["manifest"])["name"] for provider in initial_providers
    } == set(PROVIDER_MATRIX)

    loaded = manage_providers(action="load_module", module="temp_provider_load")
    assert loaded["status"] == "error"
    assert loaded["action"] == "load_module"
    assert loaded["error"] == "action=load_module is disabled on the public MCP surface"
    assert loaded["loaded_count"] == 0
    assert loaded["error_count"] == 0
    providers = cast(list[dict[str, object]], loaded["providers"])
    assert isinstance(providers, list)

    invalid = manage_providers(action="invalid-action")
    assert invalid["status"] == "error"
    assert invalid["action"] == "invalid-action"
    assert (
        invalid["error"] == "unsupported provider action: invalid-action; "
        "allowed actions: list, startup, shutdown"
    )
    assert {cast(dict[str, object], provider["manifest"])["name"] for provider in providers} == set(
        PROVIDER_MATRIX
    )


def test_builtin_provider_manifests_align_with_fl_surface_catalog() -> None:
    providers = builtin_providers()
    providers_by_name = {provider.manifest.name: provider.manifest for provider in providers}
    assert set(providers_by_name) == set(PROVIDER_MATRIX)

    all_tool_names = {spec.name for spec in FL_TOOL_SPECS}
    expected_task_kinds = {
        "flapi-live": set(),
        "piano-roll-script": set(),
        "midi-fallback": set(),
        "mock": {"audio", "render"},
    }

    for name, public_matrix in PROVIDER_MATRIX.items():
        manifest = providers_by_name[name]
        capabilities = set(manifest.capabilities)
        supported_domains = set(manifest.supported_domains)

        matrix_domains = cast(list[str], public_matrix["supported_domains"])
        matrix_aliases = cast(list[str], public_matrix.get("aliases", []))

        assert supported_domains == set(matrix_domains)
        assert set(manifest.aliases) == set(matrix_aliases)
        assert set(manifest.task_kinds) == expected_task_kinds[name]

        if name == "flapi-live":
            assert capabilities == all_tool_names
            assert supported_domains == {spec.domain for spec in FL_TOOL_SPECS}
            assert "mixer_get_track" in capabilities
            assert "mixer_set_track_pan" in capabilities
            assert "automation_list_clips" in capabilities
            continue
        if name == "mock":
            assert capabilities == all_tool_names
            continue
        expected_capabilities = {
            spec.name for spec in FL_TOOL_SPECS if spec.domain in supported_domains
        }
        assert capabilities == expected_capabilities


def test_flapi_live_fails_closed_without_live_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FL_MCP_BRIDGE_MODE", "mock")
    reset_provider_registry()
    registry = get_provider_registry(load_entry_points=False)

    assert registry.supports("flapi-live", "mixer_set_track_pan")

    result = registry.execute(
        "flapi-live",
        domain="mixer",
        operation="set_track_pan",
        payload={"index": 0, "pan": 0.1},
    )

    assert result.success is False
    assert result.provider == "flapi-live"
    assert result.bridge_mode == "mock"
    assert result.error_code == "live_provider_unavailable"
