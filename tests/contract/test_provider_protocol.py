"""Contract tests verifying all builtin providers implement the ProviderAdapter protocol."""

from __future__ import annotations

import pytest

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.providers.builtin import builtin_providers
from fl_mcp.schemas.provider import (
    ProviderHealthReport,
    ProviderManifest,
    ProviderOperationResult,
)
from fl_mcp.tools.fl_surface import FL_TOOL_BY_NAME

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROVIDERS = builtin_providers()
PROVIDER_IDS = [p.manifest.name for p in PROVIDERS]


@pytest.fixture(params=PROVIDERS, ids=PROVIDER_IDS)
def provider(request: pytest.FixtureRequest):
    """Yield each builtin provider in turn."""
    return request.param


# ---------------------------------------------------------------------------
# 1. Each builtin provider has all required ProviderAdapter methods
# ---------------------------------------------------------------------------

REQUIRED_METHODS = [
    "supports",
    "execute",
    "read_resource",
    "start_task",
    "poll_task",
    "cancel_task",
    "startup",
    "shutdown",
    "health",
]


@pytest.mark.parametrize("method_name", REQUIRED_METHODS)
def test_provider_has_required_method(provider, method_name: str) -> None:
    """Each builtin provider exposes every method declared by ProviderAdapter."""
    attr = getattr(provider, method_name, None)
    assert attr is not None, f"Provider '{provider.manifest.name}' missing method '{method_name}'"
    assert callable(attr), f"Provider '{provider.manifest.name}': '{method_name}' is not callable"


# ---------------------------------------------------------------------------
# 2. Each provider has a manifest with name, supported_domains, capabilities
# ---------------------------------------------------------------------------


def test_manifest_has_required_attributes(provider) -> None:
    """Provider manifest exposes name, supported_domains, and capabilities."""
    manifest = provider.manifest
    assert isinstance(manifest, ProviderManifest)
    assert isinstance(manifest.name, str) and len(manifest.name) > 0
    assert isinstance(manifest.supported_domains, list) and len(manifest.supported_domains) > 0
    assert isinstance(manifest.capabilities, list)


# ---------------------------------------------------------------------------
# 3. supports(capability) returns True for exact operations, False for others
# ---------------------------------------------------------------------------


def test_supports_declared_operation_capabilities(provider) -> None:
    """supports() returns True for exact operation capabilities in the manifest."""
    for capability in provider.manifest.capabilities:
        assert provider.supports(capability) is True, (
            f"Provider '{provider.manifest.name}' should support capability '{capability}'"
        )


def test_supports_rejects_unknown_domain(provider) -> None:
    """supports() returns False for a domain not in the manifest."""
    fake_domain = "__nonexistent_domain_for_testing__"
    assert provider.supports(fake_domain) is False, (
        f"Provider '{provider.manifest.name}' should not support '{fake_domain}'"
    )


# ---------------------------------------------------------------------------
# 4. execute() returns a result dict for supported operation capabilities
# ---------------------------------------------------------------------------


def test_execute_supported_operation_returns_result(provider) -> None:
    """execute() on a supported operation returns a ProviderOperationResult."""
    if not provider.manifest.capabilities:
        pytest.skip("Provider has no capabilities")
    capability = provider.manifest.capabilities[0]
    spec = FL_TOOL_BY_NAME[capability]
    result = provider.execute(domain=spec.domain, operation=spec.operation, payload={})
    assert isinstance(result, ProviderOperationResult)
    assert isinstance(result.provider, str)
    assert result.provider == provider.manifest.name


# ---------------------------------------------------------------------------
# 5. execute() returns error for unsupported domains
# ---------------------------------------------------------------------------


def test_execute_unsupported_domain_returns_error(provider) -> None:
    """execute() on an unsupported domain returns a failing ProviderOperationResult."""
    result = provider.execute(
        domain="__unsupported__",
        operation="noop",
        payload={},
    )
    assert isinstance(result, ProviderOperationResult)
    assert result.success is False
    assert result.error_code is not None


# ---------------------------------------------------------------------------
# 6. health() returns a dict with health information
# ---------------------------------------------------------------------------


def test_health_returns_report(provider) -> None:
    """health() returns a ProviderHealthReport with status and details."""
    report = provider.health()
    assert isinstance(report, ProviderHealthReport)
    assert report.status in {"ok", "warning", "error", "disabled"}
    assert isinstance(report.details, dict)


# ---------------------------------------------------------------------------
# 7. startup() and shutdown() complete without error
# ---------------------------------------------------------------------------


def test_startup_and_shutdown_succeed(provider) -> None:
    """startup() and shutdown() execute without raising."""
    # Shutdown first to clear any prior state, then startup/shutdown cycle.
    provider.shutdown()
    provider.startup()
    provider.shutdown()


# ---------------------------------------------------------------------------
# 8. Provider manifests have unique names
# ---------------------------------------------------------------------------


def test_provider_manifest_names_unique() -> None:
    """All builtin providers have distinct manifest names."""
    names = [p.manifest.name for p in PROVIDERS]
    assert len(names) == len(set(names)), f"Duplicate provider names detected: {names}"


# ---------------------------------------------------------------------------
# 9. All declared domains in manifests are in canonical DOMAINS tuple
# ---------------------------------------------------------------------------


def test_declared_domains_are_canonical(provider) -> None:
    """Every domain listed in a provider manifest is in the canonical DOMAINS tuple."""
    canonical = set(DOMAINS)
    for domain in provider.manifest.supported_domains:
        assert domain in canonical, (
            f"Provider '{provider.manifest.name}' declares non-canonical domain '{domain}'. "
            f"Canonical domains: {sorted(canonical)}"
        )


# ---------------------------------------------------------------------------
# 10. The "mock" provider supports all 16 canonical domains
# ---------------------------------------------------------------------------


def test_mock_provider_supports_all_canonical_domains() -> None:
    """The mock provider must cover every domain in the canonical DOMAINS tuple."""
    mock = next((p for p in PROVIDERS if p.manifest.name == "mock"), None)
    assert mock is not None, "No mock provider found in builtin_providers()"
    canonical = set(DOMAINS)
    supported = set(mock.manifest.supported_domains)
    missing = canonical - supported
    assert not missing, f"Mock provider is missing canonical domains: {sorted(missing)}"
    assert len(supported) == len(DOMAINS), (
        f"Expected mock to support {len(DOMAINS)} domains, got {len(supported)}"
    )
