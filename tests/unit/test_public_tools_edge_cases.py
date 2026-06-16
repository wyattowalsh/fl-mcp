"""Edge case tests for all public MCP tool handlers in fl_mcp.tools.public."""

from __future__ import annotations

import pytest

from fl_mcp.providers.runtime import reset_provider_registry
from fl_mcp.runtime.state import reset_runtime_state
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.tools.public import (
    analyze_audio,
    apply_changes,
    inspect_runtime,
    manage_providers,
    plan_changes,
    query_project,
    render_project,
)


@pytest.fixture(autouse=True)
def _clean_singletons() -> None:
    """Reset global singletons before each test for isolation."""
    reset_runtime_state()
    reset_provider_registry()


# ---------------------------------------------------------------------------
# query_project edge cases
# ---------------------------------------------------------------------------


class TestQueryProjectEdgeCases:
    """Edge cases for the query_project tool handler."""

    def test_no_graph_uses_runtime_state(self) -> None:
        """query_project('transport') with no graph falls back to runtime state."""
        result = query_project("transport")
        assert isinstance(result, dict)
        assert result["domain"] == "transport"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_empty_dict_graph_validates_to_empty_project(self) -> None:
        """query_project('transport', {}) coerces empty dict to empty ProjectGraph."""
        result = query_project("transport", {})
        assert isinstance(result, dict)
        assert result["domain"] == "transport"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_nonexistent_domain_returns_empty_projection(self) -> None:
        """query_project('nonexistent_domain') returns an empty projection, not an error."""
        result = query_project("nonexistent_domain")
        assert isinstance(result, dict)
        assert result["domain"] == "nonexistent_domain"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_invalid_graph_type_string_returns_error(self) -> None:
        """query_project with a string graph returns an error dict."""
        result = query_project("transport", "not-a-graph")  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "query_project"
        assert "error" in result

    def test_invalid_graph_type_int_returns_error(self) -> None:
        """query_project with an integer graph returns an error dict."""
        result = query_project("transport", 42)  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "query_project"

    def test_graph_with_nodes_filters_by_domain(self) -> None:
        """query_project projects only nodes matching the requested domain."""
        graph = {
            "nodes": [
                {"id": "n1", "kind": "transport", "data": {}},
                {"id": "n2", "kind": "mixer", "data": {}},
            ],
            "edges": [],
        }
        result = query_project("transport", graph)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "n1"

    def test_graph_with_subdomain_kind_matches(self) -> None:
        """query_project matches node kinds that start with 'domain.'."""
        graph = {
            "nodes": [
                {"id": "n1", "kind": "transport.bpm", "data": {}},
            ],
            "edges": [],
        }
        result = query_project("transport", graph)
        assert len(result["nodes"]) == 1

    def test_graph_override_does_not_mutate_runtime_state(self) -> None:
        """query_project uses graph overrides ephemerally without storing them."""
        graph = {
            "nodes": [
                {"id": "n1", "kind": "transport", "data": {}},
            ],
            "edges": [],
        }

        override_result = query_project("transport", graph)
        runtime_result = query_project("transport")

        assert override_result["nodes"][0]["id"] == "n1"
        assert runtime_result["nodes"] == []

    def test_legacy_graph_first_signature_still_projects(self) -> None:
        """query_project keeps supporting the legacy (graph, domain) call shape."""
        graph = {
            "nodes": [
                {"id": "n1", "kind": "transport", "data": {}},
                {"id": "n2", "kind": "mixer", "data": {}},
            ],
            "edges": [],
        }

        result = query_project(graph, "transport")

        assert result["domain"] == "transport"
        assert [node["id"] for node in result["nodes"]] == ["n1"]


# ---------------------------------------------------------------------------
# plan_changes edge cases
# ---------------------------------------------------------------------------


class TestPlanChangesEdgeCases:
    """Edge cases for the plan_changes tool handler."""

    def test_empty_changes_returns_planned_with_warning(self) -> None:
        """plan_changes with changes=[] returns planned status and a warning."""
        envelope = TransactionEnvelope(
            request_id="plan-empty-1",
            mode="preview",
            changes=[],
        )
        result = plan_changes(envelope)
        assert isinstance(result, dict)
        assert result["status"] == "planned"
        assert "No changes requested" in result.get("warnings", [])

    def test_invalid_envelope_missing_fields_returns_error(self) -> None:
        """plan_changes with a raw dict (not TransactionEnvelope) returns error dict.

        The handler catches ValidationError, TypeError, and AttributeError so
        that raw dicts that bypass the type hint are handled gracefully.
        """
        result = plan_changes({})  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "plan_changes"
        assert "changes" in result["error"]

    def test_none_envelope_returns_error(self) -> None:
        """plan_changes(None) returns error dict (no .changes on NoneType)."""
        result = plan_changes(None)  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "plan_changes"

    def test_single_change_produces_per_domain_result(self) -> None:
        """plan_changes with a single valid change produces a per-domain result entry."""
        envelope = TransactionEnvelope(
            request_id="plan-single-1",
            mode="preview",
            changes=[
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "checkpointed",
                }
            ],
        )
        result = plan_changes(envelope)
        assert result["status"] == "planned"
        assert len(result["per_domain_results"]) >= 1
        diff = result.get("diff_summary", {})
        assert diff.get("change_count") == 1


# ---------------------------------------------------------------------------
# apply_changes edge cases
# ---------------------------------------------------------------------------


class TestApplyChangesEdgeCases:
    """Edge cases for the apply_changes tool handler."""

    def test_preview_mode_returns_planned_without_executing(self) -> None:
        """apply_changes with mode='preview' returns planned status, no execution."""
        envelope = TransactionEnvelope(
            request_id="apply-preview-1",
            mode="preview",
            changes=[
                {
                    "domain": "mixer",
                    "operation": "set_volume",
                    "rollback_class": "checkpointed",
                }
            ],
        )
        result = apply_changes(envelope)
        assert isinstance(result, dict)
        assert result["status"] == "planned"
        diff = result.get("diff_summary", {})
        assert diff.get("mode") == "preview"
        assert diff.get("applied_count") == 0

    def test_preview_mode_empty_changes(self) -> None:
        """apply_changes preview mode with no changes still returns planned."""
        envelope = TransactionEnvelope(
            request_id="apply-preview-empty",
            mode="preview",
            changes=[],
        )
        result = apply_changes(envelope)
        assert result["status"] == "planned"
        assert result.get("diff_summary", {}).get("change_count") == 0

    def test_none_envelope_returns_error(self) -> None:
        """apply_changes(None) returns error dict (no .mode on NoneType)."""
        result = apply_changes(None)  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "apply_changes"

    def test_dict_envelope_returns_error(self) -> None:
        """apply_changes({}) returns error dict (dict has no .mode)."""
        result = apply_changes({})  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["tool"] == "apply_changes"


# ---------------------------------------------------------------------------
# render_project edge cases
# ---------------------------------------------------------------------------


class TestRenderProjectEdgeCases:
    """Edge cases for the render_project tool handler."""

    def test_none_request_uses_defaults(self) -> None:
        """render_project(None) dispatches with default RenderExportRequest."""
        result = render_project(None)
        assert isinstance(result, dict)
        # The handler should return a dict; it may have task info or status
        assert "status" not in result or result.get("status") != "error"

    def test_empty_dict_request(self) -> None:
        """render_project({}) validates empty dict to default RenderExportRequest."""
        result = render_project({})  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert "status" not in result or result.get("status") != "error"

    def test_invalid_request_returns_error(self) -> None:
        """render_project with invalid request type returns error dict."""
        result = render_project("bad")  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result.get("status") == "error"
        assert result.get("tool") == "render_project"


# ---------------------------------------------------------------------------
# analyze_audio edge cases
# ---------------------------------------------------------------------------


class TestAnalyzeAudioEdgeCases:
    """Edge cases for the analyze_audio tool handler."""

    def test_none_request_uses_defaults(self) -> None:
        """analyze_audio(None) dispatches with default AudioAnalyzeRequest."""
        result = analyze_audio(None)
        assert isinstance(result, dict)
        assert "status" not in result or result.get("status") != "error"

    def test_empty_dict_request(self) -> None:
        """analyze_audio({}) validates empty dict to default AudioAnalyzeRequest."""
        result = analyze_audio({})  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert "status" not in result or result.get("status") != "error"

    def test_invalid_request_returns_error(self) -> None:
        """analyze_audio with invalid request type returns error dict."""
        result = analyze_audio(12345)  # type: ignore[arg-type]
        assert isinstance(result, dict)
        assert result.get("status") == "error"
        assert result.get("tool") == "analyze_audio"


# ---------------------------------------------------------------------------
# inspect_runtime edge cases
# ---------------------------------------------------------------------------


class TestInspectRuntimeEdgeCases:
    """Edge cases for the inspect_runtime tool handler."""

    def test_no_args_returns_dict_with_expected_keys(self) -> None:
        """inspect_runtime() with no args returns a dict with core keys."""
        result = inspect_runtime()
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["tool"] == "inspect_runtime"
        assert "transport" in result
        assert "capabilities" in result
        assert "tools" in result
        assert "resources" in result
        assert "prompts" in result
        assert "providers" in result
        assert "fl_capabilities" in result
        assert "provider_matrix" in result

    def test_capabilities_counts_match_inputs(self) -> None:
        """inspect_runtime capabilities counts reflect the passed-in lists."""
        tools = [{"name": "tool_a"}, {"name": "tool_b"}]
        resources = [{"uri": "res://1", "name": "r1"}]
        prompts = [{"name": "p1"}]
        result = inspect_runtime(
            tools=tools,
            resources=resources,
            prompts=prompts,
        )
        caps = result["capabilities"]
        assert caps["tool_count"] == 2
        assert caps["resource_count"] == 1
        assert caps["prompt_count"] == 1

    def test_transport_and_auth_passthrough(self) -> None:
        """inspect_runtime passes transport and auth_required through."""
        result = inspect_runtime(
            transport="stdio",
            auth_required=True,
        )
        assert result["transport"] == "stdio"
        assert result["auth_required"] is True

    def test_runtime_health_data_passthrough(self) -> None:
        """inspect_runtime includes custom runtime_health_data."""
        health = {"bridge": "connected", "latency_ms": "12"}
        result = inspect_runtime(runtime_health_data=health)
        assert result["runtime_health"] == health

    def test_fastmcp_runtime_flag(self) -> None:
        """inspect_runtime passes fastmcp_runtime flag."""
        result_true = inspect_runtime(fastmcp_runtime=True)
        assert result_true["fastmcp_runtime"] is True
        result_none = inspect_runtime(fastmcp_runtime=None)
        assert result_none["fastmcp_runtime"] is None


# ---------------------------------------------------------------------------
# manage_providers edge cases
# ---------------------------------------------------------------------------


class TestManageProvidersEdgeCases:
    """Edge cases for the manage_providers tool handler."""

    def test_list_action_returns_provider_list(self) -> None:
        """manage_providers('list') returns status ok with provider info."""
        result = manage_providers("list")
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["action"] == "list"
        assert "providers" in result
        assert "provider_count" in result

    def test_discover_action(self) -> None:
        """manage_providers('discover') returns a deterministic public-surface error."""
        result = manage_providers("discover")
        assert isinstance(result, dict)
        assert result["action"] == "discover"
        assert result["status"] == "error"
        assert result["error"] == "action=discover is disabled on the public MCP surface"
        assert result["loaded"] == []
        assert result["errors"] == []

    def test_startup_action(self) -> None:
        """manage_providers('startup') starts all registered providers."""
        result = manage_providers("startup")
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["action"] == "startup"
        assert "started" in result
        assert isinstance(result["started"], int)

    def test_shutdown_action(self) -> None:
        """manage_providers('shutdown') stops all registered providers."""
        result = manage_providers("shutdown")
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["action"] == "shutdown"
        assert "stopped" in result
        assert isinstance(result["stopped"], int)

    def test_unknown_action_returns_error(self) -> None:
        """manage_providers('unknown_action') returns a deterministic error."""
        result = manage_providers("unknown_action")
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["action"] == "unknown_action"
        assert (
            result["error"] == "unsupported provider action: unknown_action; "
            "allowed actions: list, startup, shutdown"
        )
        assert "providers" in result

    def test_load_module_action_is_disabled(self) -> None:
        """manage_providers('load_module') returns a deterministic public-surface error."""
        result = manage_providers("load_module", module="temp_provider_load")
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["action"] == "load_module"
        assert result["error"] == "action=load_module is disabled on the public MCP surface"

    def test_default_action_parameter(self) -> None:
        """manage_providers() with no action defaults to 'list'."""
        result = manage_providers()
        assert result["action"] == "list"
        assert result["status"] == "ok"

    def test_startup_then_shutdown_counts(self) -> None:
        """startup then shutdown returns consistent started/stopped counts."""
        start_result = manage_providers("startup")
        stop_result = manage_providers("shutdown")
        # Both should reflect the same count of builtin providers
        assert start_result["started"] == stop_result["stopped"]
