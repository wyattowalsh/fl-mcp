"""Tests for the resources-first read surface."""

from __future__ import annotations

from fl_mcp.resources.surface import (
    audio_analysis,
    domain_operations,
    project_arrangement,
    project_snapshot,
    provider_matrix,
    render_job,
    runtime_capabilities,
)


def test_project_snapshot_returns_dict_with_data_key() -> None:
    result = project_snapshot()
    assert isinstance(result, dict)
    assert "data" in result
    assert "resource" in result
    assert result["resource"] == "project://snapshot"


def test_project_snapshot_data_contains_graph_structure() -> None:
    result = project_snapshot()
    data = result["data"]
    # ProjectGraph model_dump produces a dict with known keys
    assert isinstance(data, dict)


def test_project_arrangement_returns_dict_with_data_key() -> None:
    result = project_arrangement()
    assert isinstance(result, dict)
    assert "data" in result
    assert "resource" in result
    assert result["resource"] == "project://arrangement"


def test_project_arrangement_data_contains_arrangement_structure() -> None:
    result = project_arrangement()
    data = result["data"]
    assert isinstance(data, dict)
    assert "selected_arrangement" in data
    assert "tracks" in data
    assert "markers" in data


def test_runtime_capabilities_returns_dict_with_known_structure() -> None:
    result = runtime_capabilities()
    assert isinstance(result, dict)
    assert "resource" in result
    assert result["resource"] == "runtime://capabilities"
    assert "data" in result
    data = result["data"]
    assert isinstance(data, dict)
    assert "providers" in data
    assert "tools" in data
    assert "domains" in data


def test_runtime_capabilities_domains_is_sorted_list() -> None:
    result = runtime_capabilities()
    data = result["data"]
    domains = data["domains"]
    assert isinstance(domains, list)
    assert domains == sorted(domains)


def test_provider_matrix_returns_dict_with_known_structure() -> None:
    result = provider_matrix()
    assert isinstance(result, dict)
    assert "resource" in result
    assert result["resource"] == "providers://matrix"
    assert "data" in result
    data = result["data"]
    assert isinstance(data, dict)


def test_provider_matrix_contains_known_providers() -> None:
    result = provider_matrix()
    data = result["data"]
    assert isinstance(data, dict)
    # The PROVIDER_MATRIX defines at least flapi-live and mock
    assert "flapi-live" in data or "mock" in data


def test_domain_operations_transport_returns_operations() -> None:
    result = domain_operations("transport")
    assert isinstance(result, dict)
    assert "resource" in result
    assert result["resource"] == "runtime://capabilities/transport"
    assert "data" in result
    data = result["data"]
    assert isinstance(data, dict)
    assert data["domain"] == "transport"
    assert "tools" in data
    assert "providers" in data


def test_domain_operations_normalizes_underscores() -> None:
    result = domain_operations("piano_roll")
    assert isinstance(result, dict)
    data = result["data"]
    assert data["domain"] == "piano-roll"


def test_domain_operations_unsupported_domain_returns_error() -> None:
    result = domain_operations("nonexistent_domain_xyz")
    assert isinstance(result, dict)
    data = result["data"]
    assert isinstance(data, dict)
    assert data["error"] == "unsupported_domain"
    assert data["domain"] == "nonexistent-domain-xyz"
    assert "available_domains" in data
    assert isinstance(data["available_domains"], list)
    assert data["tools"] == []


def test_render_job_nonexistent_handles_gracefully() -> None:
    result = render_job("nonexistent")
    assert isinstance(result, dict)
    assert "resource" in result
    assert result["resource"] == "render://jobs/nonexistent"
    assert "data" in result
    data = result["data"]
    assert isinstance(data, dict)
    assert data["id"] == "nonexistent"
    assert data["kind"] == "render"
    assert data["state"] == "failed"
    assert data["message"] == "unknown_job"


def test_audio_analysis_nonexistent_handles_gracefully() -> None:
    result = audio_analysis("nonexistent")
    assert isinstance(result, dict)
    assert "resource" in result
    assert result["resource"] == "audio://analyses/nonexistent"
    assert "data" in result
    data = result["data"]
    assert isinstance(data, dict)
    assert data["id"] == "nonexistent"
    assert data["kind"] == "audio-analysis"
    assert data["state"] == "failed"
    assert data["message"] == "unknown_analysis"
