"""Comprehensive tests for graph model, domains, and canonical serialization."""

from __future__ import annotations

import json

import pytest

from fl_mcp.graph.canonical import (
    _normalize_graph_payload,
    deserialize_graph,
    serialize_graph,
)
from fl_mcp.graph.domains import DOMAINS
from fl_mcp.graph.model import GraphEdge, GraphNode, ProjectGraph

# ---------------------------------------------------------------------------
# 1. ProjectGraph default construction — empty graph
# ---------------------------------------------------------------------------


class TestProjectGraphDefaults:
    def test_default_construction_is_empty(self) -> None:
        graph = ProjectGraph()
        assert graph.schema_version == "1.0"
        assert graph.nodes == []
        assert graph.edges == []

    def test_default_nodes_are_independent_lists(self) -> None:
        g1 = ProjectGraph()
        g2 = ProjectGraph()
        g1.nodes.append(GraphNode(id="x"))
        assert g2.nodes == []

    def test_default_edges_are_independent_lists(self) -> None:
        g1 = ProjectGraph()
        g2 = ProjectGraph()
        g1.edges.append(GraphEdge(source="a", target="b"))
        assert g2.edges == []


# ---------------------------------------------------------------------------
# 2. to_projection(domain) for each domain in DOMAINS returns a dict
# ---------------------------------------------------------------------------


class TestToProjectionPerDomain:
    @pytest.mark.parametrize("domain", DOMAINS)
    def test_projection_returns_dict_for_each_domain(self, domain: str) -> None:
        graph = ProjectGraph()
        result = graph.to_projection(domain)
        assert isinstance(result, dict)
        assert result["domain"] == domain
        assert result["nodes"] == []
        assert result["edges"] == []

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_projection_filters_matching_nodes(self, domain: str) -> None:
        graph = ProjectGraph(
            nodes=[
                GraphNode(id="match", kind=domain),
                GraphNode(id="sub", kind=f"{domain}.sub"),
                GraphNode(id="other", kind="__nonexistent__"),
            ],
        )
        proj = graph.to_projection(domain)
        node_ids = {n["id"] for n in proj["nodes"]}
        assert "match" in node_ids
        assert "sub" in node_ids
        assert "other" not in node_ids


# ---------------------------------------------------------------------------
# 3. to_projection("nonexistent") — returns dict with empty lists
# ---------------------------------------------------------------------------


class TestToProjectionNonexistent:
    def test_nonexistent_domain_returns_empty_projection(self) -> None:
        graph = ProjectGraph(
            nodes=[GraphNode(id="n1", kind="mixer.channel")],
            edges=[GraphEdge(source="n1", target="n1", kind="self")],
        )
        result = graph.to_projection("nonexistent")
        assert isinstance(result, dict)
        assert result["domain"] == "nonexistent"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_empty_string_domain_returns_empty_projection(self) -> None:
        graph = ProjectGraph(
            nodes=[GraphNode(id="n1", kind="mixer")],
        )
        result = graph.to_projection("")
        assert result["nodes"] == []


# ---------------------------------------------------------------------------
# 4. Graph roundtrip: construct -> model_dump -> model_validate -> assert equal
# ---------------------------------------------------------------------------


class TestGraphRoundtrip:
    def test_empty_graph_roundtrip(self) -> None:
        original = ProjectGraph()
        dumped = original.model_dump()
        restored = ProjectGraph.model_validate(dumped)
        assert restored == original

    def test_populated_graph_roundtrip(self) -> None:
        original = ProjectGraph(
            schema_version="2.0",
            nodes=[
                GraphNode(id="ch1", kind="channels", data={"volume": 0.8}),
                GraphNode(id="pat1", kind="patterns.clip", data={"length": 16}),
            ],
            edges=[
                GraphEdge(source="ch1", target="pat1", kind="contains"),
            ],
        )
        dumped = original.model_dump()
        restored = ProjectGraph.model_validate(dumped)
        assert restored == original
        assert restored.schema_version == "2.0"
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1

    def test_roundtrip_preserves_node_data(self) -> None:
        original = ProjectGraph(
            nodes=[
                GraphNode(
                    id="n1",
                    kind="plugins",
                    data={"name": "Sytrus", "preset": "Default", "slots": [1, 2, 3]},
                ),
            ],
        )
        dumped = original.model_dump()
        restored = ProjectGraph.model_validate(dumped)
        assert restored.nodes[0].data == original.nodes[0].data


# ---------------------------------------------------------------------------
# 5. Graph JSON serialization roundtrip
# ---------------------------------------------------------------------------


class TestGraphJsonRoundtrip:
    def test_empty_graph_json_roundtrip(self) -> None:
        original = ProjectGraph()
        json_str = original.model_dump_json()
        restored = ProjectGraph.model_validate_json(json_str)
        assert restored == original

    def test_populated_graph_json_roundtrip(self) -> None:
        original = ProjectGraph(
            nodes=[
                GraphNode(id="m1", kind="mixer.bus", data={"gain": -3.5}),
                GraphNode(id="m2", kind="mixer.channel", data={"muted": True}),
            ],
            edges=[
                GraphEdge(source="m1", target="m2", kind="routes"),
            ],
        )
        json_str = original.model_dump_json()
        restored = ProjectGraph.model_validate_json(json_str)
        assert restored == original

    def test_json_roundtrip_produces_valid_json(self) -> None:
        graph = ProjectGraph(
            nodes=[GraphNode(id="x", kind="ui", data={"key": "value"})],
        )
        json_str = graph.model_dump_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "nodes" in parsed
        assert "edges" in parsed
        assert "schema_version" in parsed


# ---------------------------------------------------------------------------
# 6. DOMAINS tuple contains exactly 16 entries
# ---------------------------------------------------------------------------


class TestDomainsCount:
    def test_domains_has_exactly_16_entries(self) -> None:
        assert len(DOMAINS) == 16

    def test_domains_is_a_tuple(self) -> None:
        assert isinstance(DOMAINS, tuple)

    def test_domains_has_no_duplicates(self) -> None:
        assert len(DOMAINS) == len(set(DOMAINS))


# ---------------------------------------------------------------------------
# 7. All DOMAINS entries are lowercase strings
# ---------------------------------------------------------------------------


class TestDomainsCase:
    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_is_string(self, domain: str) -> None:
        assert isinstance(domain, str)

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_is_lowercase(self, domain: str) -> None:
        assert domain == domain.lower(), f"Domain {domain!r} is not lowercase"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_domain_is_non_empty(self, domain: str) -> None:
        assert len(domain) > 0


# ---------------------------------------------------------------------------
# 8. DOMAINS contains expected entries
# ---------------------------------------------------------------------------


class TestDomainsExpectedEntries:
    @pytest.mark.parametrize(
        "expected",
        ["transport", "mixer", "channels", "device", "arrangement"],
    )
    def test_expected_domain_present(self, expected: str) -> None:
        assert expected in DOMAINS

    def test_all_expected_domains_present_at_once(self) -> None:
        required = {"transport", "mixer", "channels", "device", "arrangement"}
        assert required.issubset(set(DOMAINS))


# ---------------------------------------------------------------------------
# 9. ProjectGraph.model_json_schema() produces valid JSON schema
# ---------------------------------------------------------------------------


class TestModelJsonSchema:
    def test_schema_is_dict(self) -> None:
        schema = ProjectGraph.model_json_schema()
        assert isinstance(schema, dict)

    def test_schema_has_properties(self) -> None:
        schema = ProjectGraph.model_json_schema()
        assert "properties" in schema
        props = schema["properties"]
        assert "schema_version" in props
        assert "nodes" in props
        assert "edges" in props

    def test_schema_serializable_to_json(self) -> None:
        schema = ProjectGraph.model_json_schema()
        json_str = json.dumps(schema)
        reloaded = json.loads(json_str)
        assert reloaded == schema

    def test_schema_has_title(self) -> None:
        schema = ProjectGraph.model_json_schema()
        assert "title" in schema
        assert schema["title"] == "ProjectGraph"


# ---------------------------------------------------------------------------
# 10. serialize_graph({}) returns valid JSON string
# ---------------------------------------------------------------------------


class TestSerializeGraph:
    def test_empty_dict_returns_valid_json(self) -> None:
        result = serialize_graph({})
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_empty_dict_has_defaults(self) -> None:
        result = serialize_graph({})
        parsed = json.loads(result)
        assert parsed["schema_version"] == "1.0"
        assert parsed["nodes"] == []
        assert parsed["edges"] == []

    def test_serialize_with_nodes(self) -> None:
        data: dict[str, object] = {
            "nodes": [{"id": "n1", "kind": "mixer", "data": {}}],
        }
        result = serialize_graph(data)
        parsed = json.loads(result)
        assert len(parsed["nodes"]) == 1
        assert parsed["nodes"][0]["id"] == "n1"

    def test_serialize_produces_compact_json(self) -> None:
        result = serialize_graph({})
        # Compact separators: no spaces after "," or ":"
        assert " " not in result or result == result.replace(": ", ":").replace(", ", ",")


# ---------------------------------------------------------------------------
# 11. deserialize_graph(serialize_graph(data)) roundtrips
# ---------------------------------------------------------------------------


class TestCanonicalRoundtrip:
    def test_empty_roundtrip(self) -> None:
        original: dict[str, object] = {}
        result = deserialize_graph(serialize_graph(original))
        assert result["schema_version"] == "1.0"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_populated_roundtrip(self) -> None:
        original: dict[str, object] = {
            "schema_version": "2.0",
            "nodes": [
                {"id": "a", "kind": "mixer", "data": {"vol": 1}},
                {"id": "b", "kind": "channels", "data": {}},
            ],
            "edges": [
                {"source": "a", "target": "b", "kind": "link"},
            ],
        }
        result = deserialize_graph(serialize_graph(original))
        assert result["schema_version"] == "2.0"
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_roundtrip_preserves_node_data(self) -> None:
        original: dict[str, object] = {
            "nodes": [
                {"id": "x", "kind": "plugins", "data": {"name": "Harmor", "version": 2}},
            ],
        }
        result = deserialize_graph(serialize_graph(original))
        node = result["nodes"][0]
        assert node["data"] == {"name": "Harmor", "version": 2}

    def test_roundtrip_normalizes_node_order(self) -> None:
        original: dict[str, object] = {
            "nodes": [
                {"id": "z", "kind": "audio"},
                {"id": "a", "kind": "audio"},
            ],
        }
        result = deserialize_graph(serialize_graph(original))
        ids = [n["id"] for n in result["nodes"]]
        assert ids == ["a", "z"]


# ---------------------------------------------------------------------------
# 12. _normalize_graph_payload sorts keys deterministically
# ---------------------------------------------------------------------------


class TestNormalizeGraphPayload:
    def test_nodes_sorted_by_id(self) -> None:
        payload: dict[str, object] = {
            "nodes": [
                {"id": "c", "kind": "mixer"},
                {"id": "a", "kind": "mixer"},
                {"id": "b", "kind": "mixer"},
            ],
        }
        normalized = _normalize_graph_payload(payload)
        ids = [n["id"] for n in normalized["nodes"]]
        assert ids == ["a", "b", "c"]

    def test_nodes_sorted_by_kind_as_tiebreaker(self) -> None:
        payload: dict[str, object] = {
            "nodes": [
                {"id": "x", "kind": "zebra"},
                {"id": "x", "kind": "alpha"},
            ],
        }
        normalized = _normalize_graph_payload(payload)
        kinds = [n["kind"] for n in normalized["nodes"]]
        assert kinds == ["alpha", "zebra"]

    def test_edges_sorted_by_source_target_kind(self) -> None:
        payload: dict[str, object] = {
            "edges": [
                {"source": "b", "target": "a", "kind": "x"},
                {"source": "a", "target": "b", "kind": "y"},
                {"source": "a", "target": "b", "kind": "x"},
            ],
        }
        normalized = _normalize_graph_payload(payload)
        edge_tuples = [(e["source"], e["target"], e["kind"]) for e in normalized["edges"]]
        assert edge_tuples == [("a", "b", "x"), ("a", "b", "y"), ("b", "a", "x")]

    def test_normalize_adds_defaults(self) -> None:
        normalized = _normalize_graph_payload({})
        assert normalized["schema_version"] == "1.0"
        assert normalized["nodes"] == []
        assert normalized["edges"] == []

    def test_determinism_across_calls(self) -> None:
        payload: dict[str, object] = {
            "nodes": [
                {"id": "b", "kind": "audio", "data": {"x": 1}},
                {"id": "a", "kind": "audio", "data": {"y": 2}},
            ],
            "edges": [
                {"source": "b", "target": "a", "kind": "link"},
                {"source": "a", "target": "b", "kind": "link"},
            ],
        }
        first = _normalize_graph_payload(payload)
        second = _normalize_graph_payload(payload)
        assert first == second

    def test_serialize_determinism(self) -> None:
        payload: dict[str, object] = {
            "nodes": [
                {"id": "b", "kind": "audio", "data": {"x": 1}},
                {"id": "a", "kind": "audio", "data": {"y": 2}},
            ],
            "edges": [
                {"source": "b", "target": "a"},
                {"source": "a", "target": "b"},
            ],
        }
        s1 = serialize_graph(payload)
        s2 = serialize_graph(payload)
        assert s1 == s2
