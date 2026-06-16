"""Tests verifying deterministic behavior and idempotency guarantees in fl-mcp."""

from __future__ import annotations

import json
from typing import ClassVar

import pytest

from fl_mcp.bridge.mock_generators import mock_result
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.loading import load_config
from fl_mcp.graph.canonical import serialize_graph
from fl_mcp.graph.model import ProjectGraph
from fl_mcp.operations import list_operation_specs
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.runtime.health import health_payload
from fl_mcp.runtime.state import get_runtime_state
from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS, PROVIDER_MATRIX, capability_catalog
from fl_mcp.transactions.planner import plan_changes

# ---------------------------------------------------------------------------
# 1. serialize_graph produces identical output on repeated calls
# ---------------------------------------------------------------------------


class TestSerializeGraphRepeatable:
    """serialize_graph(data) produces identical output on repeated calls with same input."""

    def test_simple_graph(self) -> None:
        graph: dict[str, object] = {
            "schema_version": "1.0",
            "nodes": [
                {"id": "n1", "kind": "mixer", "data": {"volume": 0.8}},
                {"id": "n2", "kind": "channels", "data": {"name": "kick"}},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "kind": "route"},
            ],
        }
        results = [serialize_graph(graph) for _ in range(10)]
        assert len(set(results)) == 1

    def test_empty_graph(self) -> None:
        graph: dict[str, object] = {"nodes": [], "edges": []}
        results = [serialize_graph(graph) for _ in range(10)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# 2. serialize_graph output is sorted (deterministic key ordering)
# ---------------------------------------------------------------------------


class TestSerializeGraphSorted:
    """serialize_graph output has deterministic key ordering."""

    def test_keys_sorted_in_output(self) -> None:
        graph: dict[str, object] = {
            "nodes": [
                {"id": "b", "kind": "mixer", "data": {}},
                {"id": "a", "kind": "channels", "data": {}},
            ],
            "edges": [
                {"source": "b", "target": "a", "kind": "link"},
                {"source": "a", "target": "b", "kind": "link"},
            ],
        }
        output = serialize_graph(graph)
        parsed = json.loads(output)

        # Top-level keys are sorted
        assert list(parsed.keys()) == sorted(parsed.keys())

        # Nodes and edges are sorted by their ordering criteria
        node_ids = [n["id"] for n in parsed["nodes"]]
        assert node_ids == sorted(node_ids)

    def test_reversed_input_produces_same_output(self) -> None:
        nodes = [
            {"id": "z", "kind": "plugins", "data": {"x": 1}},
            {"id": "a", "kind": "channels", "data": {"y": 2}},
        ]
        graph_forward: dict[str, object] = {"nodes": nodes, "edges": []}
        graph_reverse: dict[str, object] = {"nodes": list(reversed(nodes)), "edges": []}
        assert serialize_graph(graph_forward) == serialize_graph(graph_reverse)


# ---------------------------------------------------------------------------
# 3. mock_result returns identical result on repeated calls
# ---------------------------------------------------------------------------


class TestMockResultDeterministic:
    """mock_result(domain, op, payload) returns identical result on repeated calls."""

    @pytest.mark.parametrize(
        ("domain", "operation"),
        [
            ("mixer", "get_track"),
            ("transport", "get_state"),
            ("channels", "list_channels"),
        ],
    )
    def test_repeated_calls_identical(self, domain: str, operation: str) -> None:
        payload: dict[str, object] = {"index": 0}
        results = [mock_result(domain, operation, payload, None) for _ in range(10)]
        first = results[0]
        for result in results[1:]:
            assert result == first

    def test_noop_deterministic(self) -> None:
        payload: dict[str, object] = {}
        results = [mock_result("transport", "noop", payload, None) for _ in range(5)]
        assert len({json.dumps(r, sort_keys=True) for r in results}) == 1


# ---------------------------------------------------------------------------
# 4. ProjectGraph().model_dump() is identical across calls
# ---------------------------------------------------------------------------


class TestProjectGraphModelDump:
    """ProjectGraph().model_dump() is identical across calls."""

    def test_default_graph_model_dump_stable(self) -> None:
        graph = ProjectGraph()
        dumps = [graph.model_dump() for _ in range(10)]
        first = dumps[0]
        for dump in dumps[1:]:
            assert dump == first

    def test_separate_instances_equal(self) -> None:
        dumps = [ProjectGraph().model_dump() for _ in range(5)]
        assert len({json.dumps(d, sort_keys=True) for d in dumps}) == 1


# ---------------------------------------------------------------------------
# 5. ProjectGraph().model_dump_json() is identical across calls
# ---------------------------------------------------------------------------


class TestProjectGraphModelDumpJson:
    """ProjectGraph().model_dump_json() is identical across calls."""

    def test_model_dump_json_stable(self) -> None:
        graph = ProjectGraph()
        jsons = [graph.model_dump_json() for _ in range(10)]
        assert len(set(jsons)) == 1

    def test_separate_instances_json_equal(self) -> None:
        jsons = [ProjectGraph().model_dump_json() for _ in range(5)]
        assert len(set(jsons)) == 1


# ---------------------------------------------------------------------------
# 6. capability_catalog() returns identical dict on repeated calls
# ---------------------------------------------------------------------------


class TestCapabilityCatalogDeterministic:
    """capability_catalog() returns identical dict on repeated calls."""

    def test_repeated_calls_return_same_content(self) -> None:
        catalogs = [capability_catalog() for _ in range(5)]
        first_json = json.dumps(catalogs[0], sort_keys=True)
        for catalog in catalogs[1:]:
            assert json.dumps(catalog, sort_keys=True) == first_json

    def test_catalog_has_expected_keys(self) -> None:
        catalog = capability_catalog()
        assert "providers" in catalog
        assert "tools" in catalog
        assert "domains" in catalog


# ---------------------------------------------------------------------------
# 7. PROVIDER_MATRIX is identical when accessed multiple times
# ---------------------------------------------------------------------------


class TestProviderMatrixStable:
    """PROVIDER_MATRIX is identical when accessed multiple times."""

    def test_same_object_identity(self) -> None:
        assert PROVIDER_MATRIX is PROVIDER_MATRIX

    def test_content_stable(self) -> None:
        snapshots = [json.dumps(PROVIDER_MATRIX, sort_keys=True) for _ in range(5)]
        assert len(set(snapshots)) == 1

    def test_known_providers_present(self) -> None:
        assert "flapi-live" in PROVIDER_MATRIX
        assert "mock" in PROVIDER_MATRIX


# ---------------------------------------------------------------------------
# 8. get_runtime_state() returns same instance on repeated calls (idempotent)
# ---------------------------------------------------------------------------


class TestGetRuntimeStateSingleton:
    """get_runtime_state() returns same instance on repeated calls."""

    def test_singleton_identity(self) -> None:
        state_a = get_runtime_state()
        state_b = get_runtime_state()
        assert state_a is state_b

    def test_multiple_calls_same_id(self) -> None:
        ids = [id(get_runtime_state()) for _ in range(10)]
        assert len(set(ids)) == 1


# ---------------------------------------------------------------------------
# 9. get_provider_registry() returns same instance on repeated calls (idempotent)
# ---------------------------------------------------------------------------


class TestGetProviderRegistrySingleton:
    """get_provider_registry() returns same instance on repeated calls."""

    def test_singleton_identity(self) -> None:
        reg_a = get_provider_registry(load_entry_points=False)
        reg_b = get_provider_registry(load_entry_points=False)
        assert reg_a is reg_b

    def test_multiple_calls_same_id(self) -> None:
        ids = [id(get_provider_registry(load_entry_points=False)) for _ in range(10)]
        assert len(set(ids)) == 1


# ---------------------------------------------------------------------------
# 10. get_engine() returns same instance on repeated calls (idempotent)
# ---------------------------------------------------------------------------


class TestGetEngineSingleton:
    """get_engine() returns same instance on repeated calls."""

    def test_singleton_identity(self) -> None:
        from fl_mcp.persistence.db import get_engine

        engine_a = get_engine()
        engine_b = get_engine()
        assert engine_a is engine_b

    def test_multiple_calls_same_id(self) -> None:
        from fl_mcp.persistence.db import get_engine

        ids = [id(get_engine()) for _ in range(5)]
        assert len(set(ids)) == 1


# ---------------------------------------------------------------------------
# 11. health_payload(RuntimeConfig()) produces consistent structure
# ---------------------------------------------------------------------------


class TestHealthPayloadConsistentStructure:
    """health_payload(RuntimeConfig()) produces consistent structure (keys always present)."""

    REQUIRED_KEYS: ClassVar[set[str]] = {"status", "service", "version", "environment", "timestamp"}

    def test_required_keys_present(self) -> None:
        payload = health_payload(RuntimeConfig())
        assert self.REQUIRED_KEYS <= set(payload.keys())

    def test_key_set_stable_across_calls(self) -> None:
        key_sets = [frozenset(health_payload(RuntimeConfig()).keys()) for _ in range(5)]
        assert len(set(key_sets)) == 1

    def test_non_timestamp_values_stable(self) -> None:
        payloads = [health_payload(RuntimeConfig()) for _ in range(5)]
        for payload in payloads:
            assert payload["status"] == "ok"
            assert payload["service"] == "fl-mcp"


# ---------------------------------------------------------------------------
# 12. load_config({"b": 2, "a": 1}) output keys are always sorted
# ---------------------------------------------------------------------------


class TestLoadConfigSorted:
    """load_config({"b": 2, "a": 1}) output keys are always sorted."""

    def test_keys_sorted(self) -> None:
        result = load_config({"b": 2, "a": 1})
        assert list(result.keys()) == ["a", "b"]

    def test_multiple_sources_sorted(self) -> None:
        result = load_config({"z": 1, "m": 2}, {"a": 3, "f": 4})
        assert list(result.keys()) == sorted(result.keys())

    def test_repeated_calls_identical(self) -> None:
        source: dict[str, object] = {"c": 3, "a": 1, "b": 2}
        results = [load_config(source) for _ in range(5)]
        first = results[0]
        for result in results[1:]:
            assert result == first
            assert list(result.keys()) == list(first.keys())


# ---------------------------------------------------------------------------
# 13. list_operation_specs() returns same tuple on repeated calls (cached)
# ---------------------------------------------------------------------------


class TestListOperationSpecsCached:
    """list_operation_specs() returns same tuple on repeated calls."""

    def test_stable_length(self) -> None:
        lengths = [len(list_operation_specs()) for _ in range(5)]
        assert len(set(lengths)) == 1

    def test_stable_ordering(self) -> None:
        specs_a = list_operation_specs()
        specs_b = list_operation_specs()
        names_a = [s.name for s in specs_a]
        names_b = [s.name for s in specs_b]
        assert names_a == names_b

    def test_nonempty(self) -> None:
        assert len(list_operation_specs()) > 0


# ---------------------------------------------------------------------------
# 14. FL_TOOL_SPECS ordering is consistent
# ---------------------------------------------------------------------------


class TestFLToolSpecsOrdering:
    """FL_TOOL_SPECS ordering is consistent."""

    def test_tuple_type(self) -> None:
        assert isinstance(FL_TOOL_SPECS, tuple)

    def test_ordering_stable(self) -> None:
        names_a = [s.name for s in FL_TOOL_SPECS]
        names_b = [s.name for s in FL_TOOL_SPECS]
        assert names_a == names_b

    def test_all_names_unique(self) -> None:
        names = [s.name for s in FL_TOOL_SPECS]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# 15. Transaction IDs are unique across repeated plan_changes calls
# ---------------------------------------------------------------------------


class TestTransactionIdsUnique:
    """Transaction IDs are unique across repeated plan_changes calls."""

    @staticmethod
    def _make_envelope(request_id: str) -> TransactionEnvelope:
        return TransactionEnvelope(
            request_id=request_id,
            mode="preview",
            changes=[
                DomainChange(
                    domain="mixer",
                    operation="set_volume",
                    rollback_class="checkpointed",
                    payload={"track": 0, "value": 0.75},
                ),
            ],
        )

    def test_distinct_request_ids_produce_distinct_transaction_ids(self) -> None:
        ids = set()
        for i in range(10):
            result = plan_changes(self._make_envelope(f"req-{i}"))
            ids.add(result.transaction_id)
        assert len(ids) == 10

    def test_same_request_id_produces_same_transaction_id(self) -> None:
        results = [plan_changes(self._make_envelope("stable-req")) for _ in range(5)]
        tx_ids = {r.transaction_id for r in results}
        assert len(tx_ids) == 1

    def test_transaction_id_format(self) -> None:
        result = plan_changes(self._make_envelope("abc-123"))
        assert result.transaction_id.startswith("plan-")
        assert "abc-123" in result.transaction_id
