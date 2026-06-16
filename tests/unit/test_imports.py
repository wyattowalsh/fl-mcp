"""Verify all public imports resolve and there are no circular import issues."""

from __future__ import annotations

import importlib
import pathlib
import re
import types

import pytest

# ---------------------------------------------------------------------------
# 1. Top-level package import
# ---------------------------------------------------------------------------


def test_import_fl_mcp() -> None:
    """``import fl_mcp`` must succeed without errors."""
    import fl_mcp

    assert isinstance(fl_mcp, types.ModuleType)


# ---------------------------------------------------------------------------
# 2. __version__ is a string
# ---------------------------------------------------------------------------


def test_version_is_string() -> None:
    from fl_mcp import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


# ---------------------------------------------------------------------------
# 3. Exception hierarchy re-exports
# ---------------------------------------------------------------------------


def test_exception_imports() -> None:
    from fl_mcp import (
        BridgeError,
        ConfigurationError,
        FLMCPError,
        ProviderError,
        TransactionError,
    )

    for cls in (FLMCPError, BridgeError, ProviderError, TransactionError, ConfigurationError):
        assert isinstance(cls, type)
        assert issubclass(cls, Exception)

    # All four leaf exceptions derive from the base
    assert issubclass(BridgeError, FLMCPError)
    assert issubclass(ProviderError, FLMCPError)
    assert issubclass(TransactionError, FLMCPError)
    assert issubclass(ConfigurationError, FLMCPError)


# ---------------------------------------------------------------------------
# 4. Schema core exports
# ---------------------------------------------------------------------------


def test_schema_core_imports() -> None:
    from fl_mcp.schemas import DomainChange, RollbackClass, TransactionEnvelope

    assert isinstance(TransactionEnvelope, type)
    assert isinstance(DomainChange, type)
    # RollbackClass is a Literal type alias, not a class
    assert RollbackClass is not None


# ---------------------------------------------------------------------------
# 5. Newly exported provider schemas
# ---------------------------------------------------------------------------


def test_schema_provider_imports() -> None:
    from fl_mcp.schemas import ProviderAdapterTaskRecord, ProviderHealthReport

    assert isinstance(ProviderAdapterTaskRecord, type)
    assert isinstance(ProviderHealthReport, type)


# ---------------------------------------------------------------------------
# 6. ProjectGraph
# ---------------------------------------------------------------------------


def test_project_graph_import() -> None:
    from fl_mcp.graph import ProjectGraph

    assert isinstance(ProjectGraph, type)


# ---------------------------------------------------------------------------
# 7. DOMAINS
# ---------------------------------------------------------------------------


def test_domains_import() -> None:
    from fl_mcp.graph import DOMAINS

    # DOMAINS should be a non-empty collection (frozenset, set, tuple, or dict)
    assert len(DOMAINS) > 0


# ---------------------------------------------------------------------------
# 8. Public tool handlers
# ---------------------------------------------------------------------------


def test_public_tool_imports() -> None:
    from fl_mcp.tools.public import apply_changes, plan_changes, query_project

    for fn in (query_project, plan_changes, apply_changes):
        assert callable(fn)


# ---------------------------------------------------------------------------
# 9. FL surface tool specs and handlers
# ---------------------------------------------------------------------------


def test_fl_surface_imports() -> None:
    from fl_mcp.tools.fl_surface import FL_TOOL_HANDLERS, FL_TOOL_SPECS

    assert isinstance(FL_TOOL_SPECS, tuple)
    assert len(FL_TOOL_SPECS) > 0
    assert isinstance(FL_TOOL_HANDLERS, dict)
    assert len(FL_TOOL_HANDLERS) > 0


# ---------------------------------------------------------------------------
# 10. Bridge exports
# ---------------------------------------------------------------------------


def test_bridge_imports() -> None:
    from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE, FLStudioBridge

    assert isinstance(FLStudioBridge, type)
    assert isinstance(DEFAULT_BRIDGE, FLStudioBridge)


# ---------------------------------------------------------------------------
# 11. Provider registry
# ---------------------------------------------------------------------------


def test_provider_registry_import() -> None:
    from fl_mcp.providers.runtime import get_provider_registry

    assert callable(get_provider_registry)


# ---------------------------------------------------------------------------
# 12. Runtime state
# ---------------------------------------------------------------------------


def test_runtime_state_import() -> None:
    from fl_mcp.runtime.state import get_runtime_state

    assert callable(get_runtime_state)


# ---------------------------------------------------------------------------
# 13. RuntimeConfig
# ---------------------------------------------------------------------------


def test_runtime_config_import() -> None:
    from fl_mcp.config import RuntimeConfig

    assert isinstance(RuntimeConfig, type)


# ---------------------------------------------------------------------------
# 14. Settings
# ---------------------------------------------------------------------------


def test_settings_import() -> None:
    from fl_mcp.config.settings import Settings, settings

    assert isinstance(Settings, type)
    assert isinstance(settings, Settings)


# ---------------------------------------------------------------------------
# 15. Operations facade
# ---------------------------------------------------------------------------


def test_operations_imports() -> None:
    from fl_mcp.operations import execute_operation_tool, list_operation_specs

    assert callable(list_operation_specs)
    assert callable(execute_operation_tool)


# ---------------------------------------------------------------------------
# 16. Server factory
# ---------------------------------------------------------------------------


def test_server_factory_imports() -> None:
    from fl_mcp.server.factory import COMPACT_TOOL_NAMES, create_server

    assert len(COMPACT_TOOL_NAMES) == 12
    assert callable(create_server)


# ---------------------------------------------------------------------------
# 17. Exceptions module direct import
# ---------------------------------------------------------------------------


def test_exceptions_module_import() -> None:
    from fl_mcp.exceptions import FLMCPError

    assert isinstance(FLMCPError, type)
    assert issubclass(FLMCPError, Exception)


# ---------------------------------------------------------------------------
# 18. Imported objects have expected types
# ---------------------------------------------------------------------------


def test_imported_object_types() -> None:
    """Classes are types, functions/handlers are callable, collections have items."""
    from fl_mcp import FLMCPError
    from fl_mcp.bridge.fl_studio import DEFAULT_BRIDGE, FLStudioBridge
    from fl_mcp.config import RuntimeConfig
    from fl_mcp.config.settings import Settings, settings
    from fl_mcp.graph import DOMAINS, ProjectGraph
    from fl_mcp.operations import execute_operation_tool, list_operation_specs
    from fl_mcp.providers.runtime import get_provider_registry
    from fl_mcp.runtime.state import get_runtime_state
    from fl_mcp.schemas import (
        DomainChange,
        ProviderAdapterTaskRecord,
        ProviderHealthReport,
        RollbackClass,
        TransactionEnvelope,
    )
    from fl_mcp.server.factory import COMPACT_TOOL_NAMES, create_server
    from fl_mcp.tools.fl_surface import FL_TOOL_HANDLERS, FL_TOOL_SPECS
    from fl_mcp.tools.public import apply_changes, plan_changes, query_project

    # Classes
    for cls in (
        FLMCPError,
        FLStudioBridge,
        RuntimeConfig,
        Settings,
        ProjectGraph,
        TransactionEnvelope,
        DomainChange,
        ProviderAdapterTaskRecord,
        ProviderHealthReport,
    ):
        assert isinstance(cls, type), f"{cls!r} should be a type"

    # RollbackClass is a Literal type alias, not a runtime class
    assert RollbackClass is not None

    # Callables
    for fn in (
        get_provider_registry,
        get_runtime_state,
        list_operation_specs,
        execute_operation_tool,
        create_server,
        query_project,
        plan_changes,
        apply_changes,
    ):
        assert callable(fn), f"{fn!r} should be callable"

    # Instances
    assert isinstance(settings, Settings)
    assert isinstance(DEFAULT_BRIDGE, FLStudioBridge)

    # Collections
    assert isinstance(FL_TOOL_SPECS, tuple)
    assert isinstance(FL_TOOL_HANDLERS, dict)
    assert len(COMPACT_TOOL_NAMES) == 12
    assert len(DOMAINS) > 0


# ---------------------------------------------------------------------------
# 19. No ImportError for any public module under src/fl_mcp/
# ---------------------------------------------------------------------------

_SRC_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src"


def _discover_public_modules() -> list[str]:
    """Walk the fl_mcp source tree and return all importable dotted module paths."""
    fl_mcp_root = _SRC_ROOT / "fl_mcp"
    modules: list[str] = []
    for path in sorted(fl_mcp_root.rglob("*.py")):
        if path.name.startswith("_") and path.name != "__init__.py":
            continue
        relative = path.relative_to(_SRC_ROOT)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        dotted = ".".join(parts)
        modules.append(dotted)
    return modules


_PUBLIC_MODULES = _discover_public_modules()


@pytest.mark.parametrize("module_path", _PUBLIC_MODULES, ids=_PUBLIC_MODULES)
def test_public_module_importable(module_path: str) -> None:
    """Every non-private .py under src/fl_mcp/ must import without error."""
    mod = importlib.import_module(module_path)
    assert isinstance(mod, types.ModuleType)


# ---------------------------------------------------------------------------
# 20. __version__ matches pyproject.toml version
# ---------------------------------------------------------------------------


def test_version_matches_pyproject() -> None:
    from fl_mcp import __version__

    pyproject_path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject_path.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match is not None, "Could not find version in pyproject.toml"
    pyproject_version = match.group(1)
    assert __version__ == pyproject_version, (
        f"fl_mcp.__version__ ({__version__!r}) does not match "
        f"pyproject.toml version ({pyproject_version!r})"
    )
