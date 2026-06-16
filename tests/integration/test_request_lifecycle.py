"""Integration tests exercising full request lifecycles through the public tool surface.

Each test drives the complete stack: public tool -> transaction -> bridge -> mock -> result.
"""

from __future__ import annotations

import pytest

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.graph.model import GraphNode, ProjectGraph
from fl_mcp.schemas.transaction import DomainChange, TransactionEnvelope
from fl_mcp.tools.public import (
    analyze_audio,
    apply_changes,
    inspect_runtime,
    manage_providers,
    plan_changes,
    query_project,
    render_project,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(
    *,
    request_id: str = "lifecycle-test",
    mode: str = "preview",
    changes: list[DomainChange] | None = None,
    execution_policy: str = "all-or-nothing",
) -> TransactionEnvelope:
    return TransactionEnvelope(
        request_id=request_id,
        mode=mode,
        changes=changes or [],
        execution_policy=execution_policy,
    )


def _transport_change(operation: str = "set_tempo") -> DomainChange:
    return DomainChange(
        domain="transport",
        operation=operation,
        rollback_class="fully_transactional",
        payload={"bpm": 140},
    )


def _mixer_change(operation: str = "set_volume") -> DomainChange:
    return DomainChange(
        domain="mixer",
        operation=operation,
        rollback_class="checkpointed",
        payload={"track": 0, "volume": 0.8},
    )


# ---------------------------------------------------------------------------
# 1. Query -> verify
# ---------------------------------------------------------------------------


class TestQueryLifecycle:
    """query_project returns a projection with the requested domain data."""

    def test_query_transport_returns_projection(self) -> None:
        graph = ProjectGraph(
            nodes=[
                GraphNode(id="tempo-node", kind="transport", data={"bpm": 120}),
                GraphNode(id="mixer-node", kind="mixer", data={"track": 0}),
            ],
        )
        result = query_project("transport", graph=graph)

        assert result["domain"] == "transport"
        assert isinstance(result["nodes"], list)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "tempo-node"
        assert isinstance(result["edges"], list)

    def test_query_empty_domain_returns_empty_projection(self) -> None:
        graph = ProjectGraph(nodes=[])
        result = query_project("transport", graph=graph)

        assert result["domain"] == "transport"
        assert result["nodes"] == []
        assert result["edges"] == []


# ---------------------------------------------------------------------------
# 2. Plan -> verify
# ---------------------------------------------------------------------------


class TestPlanLifecycle:
    """plan_changes returns a planned result for a valid envelope."""

    def test_plan_transport_change(self) -> None:
        envelope = _make_envelope(
            mode="preview",
            changes=[_transport_change()],
        )
        result = plan_changes(envelope)

        assert result["status"] == "planned"
        assert result["transaction_id"] == "plan-lifecycle-test"
        assert "transport" in result["per_domain_results"]
        assert result["per_domain_results"]["transport"] == "planned"
        assert result["diff_summary"]["change_count"] == 1

    def test_plan_empty_envelope_warns(self) -> None:
        envelope = _make_envelope(mode="preview", changes=[])
        result = plan_changes(envelope)

        assert result["status"] == "planned"
        assert "No changes requested" in result["warnings"]


# ---------------------------------------------------------------------------
# 3. Plan -> Apply -> verify
# ---------------------------------------------------------------------------


class TestPlanApplyLifecycle:
    """apply_changes with mode='apply' returns an applied result with checkpoint."""

    def test_apply_transport_change_succeeds(self) -> None:
        envelope = _make_envelope(
            request_id="apply-test",
            mode="apply",
            changes=[_transport_change()],
        )
        result = apply_changes(envelope)

        assert result["status"] == "applied"
        assert result["transaction_id"] == "tx-apply-test"
        assert result["checkpoint_id"] is not None
        assert result["checkpoint_id"] == "ckpt-apply-test"
        assert "transport" in result["per_domain_results"]
        assert result["per_domain_results"]["transport"] == "applied"
        assert result["diff_summary"]["mode"] == "apply"
        assert result["diff_summary"]["applied_count"] == 1
        assert result["diff_summary"]["failed_count"] == 0

    def test_apply_preview_mode_returns_planned(self) -> None:
        envelope = _make_envelope(
            request_id="preview-via-apply",
            mode="preview",
            changes=[_transport_change()],
        )
        result = apply_changes(envelope)

        assert result["status"] == "planned"
        assert result["checkpoint_id"] is None


# ---------------------------------------------------------------------------
# 4. Render lifecycle
# ---------------------------------------------------------------------------


class TestRenderLifecycle:
    """render_project dispatches through the FL surface and returns a task result."""

    def test_render_returns_task_result(self) -> None:
        result = render_project()

        assert "status" in result
        assert result.get("tool") == "render_project" or "task" in result

    def test_render_with_defaults_contains_execution_keys(self) -> None:
        result = render_project()

        # The dispatch produces a task-style or direct result; either is valid.
        assert isinstance(result, dict)
        # At minimum, a status key should exist in every response path.
        assert "status" in result


# ---------------------------------------------------------------------------
# 5. Analyze lifecycle
# ---------------------------------------------------------------------------


class TestAnalyzeLifecycle:
    """analyze_audio dispatches through the FL surface and returns a task result."""

    def test_analyze_returns_task_result(self) -> None:
        result = analyze_audio()

        assert isinstance(result, dict)
        assert "status" in result

    def test_analyze_with_defaults_contains_execution_keys(self) -> None:
        result = analyze_audio()

        assert isinstance(result, dict)
        assert "status" in result


# ---------------------------------------------------------------------------
# 6. Inspect -> verify
# ---------------------------------------------------------------------------


class TestInspectLifecycle:
    """inspect_runtime returns a full runtime state snapshot."""

    def test_inspect_returns_all_sections(self) -> None:
        result = inspect_runtime(
            tools=[{"name": "test_tool", "description": "A test tool"}],
            resources=[{"uri": "test://res", "name": "test_resource"}],
            prompts=[{"name": "test_prompt"}],
            transport="stdio",
        )

        assert result["status"] == "ok"
        assert result["tool"] == "inspect_runtime"
        assert result["transport"] == "stdio"
        assert isinstance(result["capabilities"], dict)
        assert result["capabilities"]["tool_count"] == 1
        assert result["capabilities"]["resource_count"] == 1
        assert result["capabilities"]["prompt_count"] == 1
        assert result["capabilities"]["fl_tool_count"] > 0
        assert isinstance(result["tools"], list)
        assert isinstance(result["resources"], list)
        assert isinstance(result["prompts"], list)
        assert isinstance(result["fl_capabilities"], dict)
        assert isinstance(result["provider_matrix"], dict)
        assert isinstance(result["providers"], list)

    def test_inspect_empty_inputs(self) -> None:
        result = inspect_runtime()

        assert result["status"] == "ok"
        assert result["capabilities"]["tool_count"] == 0
        assert result["capabilities"]["resource_count"] == 0
        assert result["capabilities"]["prompt_count"] == 0


# ---------------------------------------------------------------------------
# 7. Manage providers lifecycle: list -> disabled discover -> startup -> shutdown
# ---------------------------------------------------------------------------


class TestManageProvidersLifecycle:
    """manage_providers keeps public lifecycle actions while blocking dynamic loading."""

    def test_list_returns_providers(self) -> None:
        result = manage_providers(action="list")

        assert result["status"] == "ok"
        assert result["action"] == "list"
        assert "provider_count" in result
        assert isinstance(result["providers"], list)

    def test_discover_returns_disabled_error(self) -> None:
        result = manage_providers(action="discover")

        assert result["status"] == "error"
        assert result["action"] == "discover"
        assert result["error"] == "action=discover is disabled on the public MCP surface"

    def test_startup_returns_started_count(self) -> None:
        result = manage_providers(action="startup")

        assert result["status"] == "ok"
        assert result["action"] == "startup"
        assert isinstance(result["started"], int)
        assert result["started"] >= 0

    def test_shutdown_returns_stopped_count(self) -> None:
        result = manage_providers(action="shutdown")

        assert result["status"] == "ok"
        assert result["action"] == "shutdown"
        assert isinstance(result["stopped"], int)
        assert result["stopped"] >= 0

    def test_public_provider_lifecycle(self) -> None:
        """Drive the public list -> disabled discover -> startup -> shutdown sequence."""
        list_result = manage_providers(action="list")
        assert list_result["status"] == "ok"

        discover_result = manage_providers(action="discover")
        assert discover_result["status"] == "error"

        startup_result = manage_providers(action="startup")
        assert startup_result["status"] == "ok"

        shutdown_result = manage_providers(action="shutdown")
        assert shutdown_result["status"] == "ok"


# ---------------------------------------------------------------------------
# 8. Multi-domain transaction: transport + mixer with allow-partial
# ---------------------------------------------------------------------------


class TestMultiDomainTransaction:
    """Envelopes with changes across multiple domains execute correctly."""

    def test_multi_domain_apply_succeeds(self) -> None:
        envelope = _make_envelope(
            request_id="multi-domain",
            mode="apply",
            changes=[_transport_change(), _mixer_change()],
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result["status"] in {"applied", "partially_applied"}
        assert result["diff_summary"]["change_count"] == 2

        per_domain = result["per_domain_results"]
        assert "transport" in per_domain
        assert "mixer" in per_domain

    def test_multi_domain_plan_succeeds(self) -> None:
        envelope = _make_envelope(
            request_id="multi-plan",
            mode="preview",
            changes=[_transport_change(), _mixer_change()],
        )
        result = plan_changes(envelope)

        assert result["status"] == "planned"
        assert result["diff_summary"]["change_count"] == 2


# ---------------------------------------------------------------------------
# 9. Error recovery: unsupported domain
# ---------------------------------------------------------------------------


class TestErrorRecovery:
    """Apply with an unsupported domain produces a clear error in the result."""

    def test_unsupported_domain_fails(self) -> None:
        bad_change = DomainChange(
            domain="nonexistent_domain",
            operation="do_something",
            rollback_class="best_effort",
            payload={},
        )
        envelope = _make_envelope(
            request_id="error-recovery",
            mode="apply",
            changes=[bad_change],
        )
        result = apply_changes(envelope)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    def test_unsupported_domain_allow_partial_with_good_change(self) -> None:
        """A mix of valid and invalid domains under allow-partial produces partial result."""
        bad_change = DomainChange(
            domain="nonexistent_domain",
            operation="do_something",
            rollback_class="best_effort",
            payload={},
        )
        envelope = _make_envelope(
            request_id="partial-error",
            mode="apply",
            changes=[_transport_change(), bad_change],
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result["status"] in {"partially_applied", "failed"}
        assert len(result["errors"]) > 0

    def test_forced_mock_failure(self) -> None:
        """A change with force_fail=True in the payload triggers a mock failure."""
        forced_fail_change = DomainChange(
            domain="transport",
            operation="set_tempo",
            rollback_class="fully_transactional",
            payload={"force_fail": True},
        )
        envelope = _make_envelope(
            request_id="forced-fail",
            mode="apply",
            changes=[forced_fail_change],
        )
        result = apply_changes(envelope)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# 10. Query all 16 domains: no crashes
# ---------------------------------------------------------------------------


class TestQueryAllDomains:
    """Querying every registered domain must not crash."""

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_query_domain_does_not_crash(self, domain: str) -> None:
        result = query_project(domain)

        assert isinstance(result, dict)
        assert result["domain"] == domain
        assert "nodes" in result
        assert "edges" in result

    def test_all_16_domains_covered(self) -> None:
        assert len(DOMAINS) == 16

    def test_query_all_domains_sequentially(self) -> None:
        """Loop through every domain and verify consistent projection shape."""
        for domain in DOMAINS:
            result = query_project(domain)

            assert isinstance(result, dict), f"Failed for domain={domain}"
            assert result["domain"] == domain
            assert isinstance(result["nodes"], list)
            assert isinstance(result["edges"], list)
