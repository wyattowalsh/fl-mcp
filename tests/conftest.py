"""Shared test fixtures for fl-mcp test suite."""

import pytest

from fl_mcp.providers.runtime import reset_provider_registry
from fl_mcp.runtime.state import reset_runtime_state


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all global singletons between tests."""
    reset_runtime_state()
    reset_provider_registry()
    yield
    reset_runtime_state()
    reset_provider_registry()


@pytest.fixture
def mock_bridge():
    """Return a FLStudioBridge instance in deterministic mock mode."""
    from fl_mcp.bridge.fl_studio import FLStudioBridge

    return FLStudioBridge(mode="mock")


@pytest.fixture
def runtime_state():
    """Return the current runtime state singleton for convenient test access."""
    from fl_mcp.runtime.state import get_runtime_state

    return get_runtime_state()


@pytest.fixture
def provider_registry():
    """Return provider registry with builtins only (no entry-point discovery)."""
    from fl_mcp.providers.runtime import get_provider_registry

    return get_provider_registry(load_entry_points=False)


@pytest.fixture
def sample_graph():
    """Return a minimal empty ProjectGraph for testing."""
    from fl_mcp.graph.model import ProjectGraph

    return ProjectGraph()


@pytest.fixture
def sample_envelope():
    """Return a minimal TransactionEnvelope in preview mode for testing."""
    from fl_mcp.schemas import TransactionEnvelope

    return TransactionEnvelope(
        request_id="test-fixture",
        mode="preview",
        changes=[],
    )
