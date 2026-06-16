"""Comprehensive tests for the FL Studio tool surface catalog."""

from __future__ import annotations

import re

from pydantic import BaseModel

from fl_mcp.graph.domains import DOMAINS
from fl_mcp.schemas.fl_tools import FLToolRequest
from fl_mcp.tools.fl_surface import (
    FL_TOOL_BY_CHANGE,
    FL_TOOL_BY_NAME,
    FL_TOOL_HANDLERS,
    FL_TOOL_SPECS,
    PROVIDER_MATRIX,
    FLToolSpec,
    capability_catalog,
    domain_capability_catalog,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_EXECUTION_MODES = {"read", "transaction", "direct"}
_REQUIRED_SPEC_ATTRS = (
    "name",
    "domain",
    "operation",
    "description",
    "request_model",
    "response_model",
    "execution_mode",
    "rollback_class",
    "tags",
    "annotations",
)
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$")


# ---------------------------------------------------------------------------
# 1. FL_TOOL_SPECS has exactly 216 entries
# ---------------------------------------------------------------------------


def test_fl_tool_specs_count() -> None:
    assert len(FL_TOOL_SPECS) == 216, f"Expected 216 tool specs, got {len(FL_TOOL_SPECS)}"


# ---------------------------------------------------------------------------
# 2. Every spec has all required attributes
# ---------------------------------------------------------------------------


def test_every_spec_has_required_attributes() -> None:
    for spec in FL_TOOL_SPECS:
        for attr in _REQUIRED_SPEC_ATTRS:
            assert hasattr(spec, attr), f"Spec {spec.name!r} missing required attribute {attr!r}"
            value = getattr(spec, attr)
            # None is acceptable for rollback_class on read tools
            if attr == "rollback_class":
                continue
            assert value is not None, f"Spec {spec.name!r} attribute {attr!r} is None"


# ---------------------------------------------------------------------------
# 3. All tool names follow underscore-separated lowercase pattern and start
#    with the domain prefix (hyphens replaced by underscores).
# ---------------------------------------------------------------------------


def test_tool_names_follow_naming_pattern() -> None:
    for spec in FL_TOOL_SPECS:
        assert _TOOL_NAME_RE.match(spec.name), (
            f"Tool name {spec.name!r} does not match pattern [a-z][a-z0-9]*(_[a-z][a-z0-9]*)*"
        )
        domain_prefix = spec.domain.replace("-", "_")
        assert spec.name.startswith(domain_prefix + "_"), (
            f"Tool name {spec.name!r} does not start with domain prefix {domain_prefix!r}"
        )


# ---------------------------------------------------------------------------
# 4. All spec domains are in the canonical DOMAINS tuple
# ---------------------------------------------------------------------------


def test_all_spec_domains_are_canonical() -> None:
    canonical = set(DOMAINS)
    for spec in FL_TOOL_SPECS:
        assert spec.domain in canonical, (
            f"Spec {spec.name!r} has domain {spec.domain!r} not in DOMAINS"
        )


# ---------------------------------------------------------------------------
# 5. All read-only tools (execution_mode="read") have rollback_class=None
# ---------------------------------------------------------------------------


def test_read_tools_have_no_rollback_class() -> None:
    for spec in FL_TOOL_SPECS:
        if spec.execution_mode == "read":
            assert spec.rollback_class is None, (
                f"Read tool {spec.name!r} should have rollback_class=None, "
                f"got {spec.rollback_class!r}"
            )


# ---------------------------------------------------------------------------
# 6. All transaction tools have non-None rollback_class
# ---------------------------------------------------------------------------


def test_transaction_tools_have_rollback_class() -> None:
    for spec in FL_TOOL_SPECS:
        if spec.execution_mode == "transaction":
            assert spec.rollback_class is not None, (
                f"Transaction tool {spec.name!r} must have a non-None rollback_class"
            )


# ---------------------------------------------------------------------------
# 7. All specs have at least 1 tag
# ---------------------------------------------------------------------------


def test_all_specs_have_at_least_one_tag() -> None:
    for spec in FL_TOOL_SPECS:
        assert len(spec.tags) >= 1, f"Spec {spec.name!r} has no tags"


# ---------------------------------------------------------------------------
# 8. FL_TOOL_HANDLERS has same count as FL_TOOL_SPECS
# ---------------------------------------------------------------------------


def test_handlers_count_matches_specs() -> None:
    assert len(FL_TOOL_HANDLERS) == len(FL_TOOL_SPECS), (
        f"Handlers count {len(FL_TOOL_HANDLERS)} != specs count {len(FL_TOOL_SPECS)}"
    )


# ---------------------------------------------------------------------------
# 9. All handler values are callable
# ---------------------------------------------------------------------------


def test_all_handlers_are_callable() -> None:
    for name, handler in FL_TOOL_HANDLERS.items():
        assert callable(handler), f"Handler for {name!r} is not callable"


# ---------------------------------------------------------------------------
# 10. FL_TOOL_BY_NAME keys match all spec names
# ---------------------------------------------------------------------------


def test_by_name_keys_match_spec_names() -> None:
    spec_names = {spec.name for spec in FL_TOOL_SPECS}
    by_name_keys = set(FL_TOOL_BY_NAME.keys())
    assert by_name_keys == spec_names, (
        f"Mismatched names: "
        f"extra in BY_NAME={by_name_keys - spec_names}, "
        f"missing from BY_NAME={spec_names - by_name_keys}"
    )


# ---------------------------------------------------------------------------
# 11. PROVIDER_MATRIX has entries for all domains with tools
# ---------------------------------------------------------------------------


def test_provider_matrix_covers_all_tool_domains() -> None:
    tool_domains = {spec.domain for spec in FL_TOOL_SPECS}
    # At least one provider must list each tool domain in its supported_domains
    covered_domains: set[str] = set()
    for provider_info in PROVIDER_MATRIX.values():
        supported = provider_info.get("supported_domains", [])
        assert isinstance(supported, list)
        covered_domains.update(supported)
    uncovered = tool_domains - covered_domains
    assert not uncovered, f"Domains with tools but no provider coverage: {uncovered}"


# ---------------------------------------------------------------------------
# 12. capability_catalog() returns a dict with expected top-level keys
# ---------------------------------------------------------------------------


def test_capability_catalog_returns_expected_keys() -> None:
    catalog = capability_catalog()
    assert isinstance(catalog, dict)
    assert "providers" in catalog
    assert "tools" in catalog
    assert "domains" in catalog
    # domains should be a sorted list of domain strings from the specs
    domains = catalog["domains"]
    assert isinstance(domains, list)
    assert len(domains) > 0


# ---------------------------------------------------------------------------
# 13. Each domain_capability_catalog entry has tools, providers, domain keys
# ---------------------------------------------------------------------------


def test_domain_capability_catalog_entries_have_required_keys() -> None:
    tool_domains = sorted({spec.domain for spec in FL_TOOL_SPECS})
    for domain in tool_domains:
        entry = domain_capability_catalog(domain)
        assert isinstance(entry, dict), (
            f"domain_capability_catalog({domain!r}) did not return a dict"
        )
        assert "tools" in entry, f"domain_capability_catalog({domain!r}) missing 'tools' key"
        assert "providers" in entry, (
            f"domain_capability_catalog({domain!r}) missing 'providers' key"
        )
        assert "domain" in entry, f"domain_capability_catalog({domain!r}) missing 'domain' key"
        assert entry["domain"] == domain
        assert isinstance(entry["tools"], list)
        assert len(entry["tools"]) > 0, f"domain_capability_catalog({domain!r}) returned no tools"


# ---------------------------------------------------------------------------
# 14. Annotations dict has readOnlyHint for read tools
# ---------------------------------------------------------------------------


def test_read_tools_have_read_only_hint_annotation() -> None:
    for spec in FL_TOOL_SPECS:
        assert "readOnlyHint" in spec.annotations, (
            f"Spec {spec.name!r} missing 'readOnlyHint' in annotations"
        )
        if spec.execution_mode == "read":
            assert spec.annotations["readOnlyHint"] is True, (
                f"Read tool {spec.name!r} should have readOnlyHint=True, "
                f"got {spec.annotations['readOnlyHint']!r}"
            )


# ---------------------------------------------------------------------------
# 15. All request_model classes are Pydantic BaseModel subclasses
# ---------------------------------------------------------------------------


def test_all_request_models_are_pydantic_base_model_subclasses() -> None:
    for spec in FL_TOOL_SPECS:
        assert issubclass(spec.request_model, BaseModel), (
            f"Spec {spec.name!r} request_model {spec.request_model!r} is not a BaseModel subclass"
        )


# ---------------------------------------------------------------------------
# Bonus structural invariants
# ---------------------------------------------------------------------------


def test_all_specs_are_fl_tool_spec_instances() -> None:
    for spec in FL_TOOL_SPECS:
        assert isinstance(spec, FLToolSpec), (
            f"Item in FL_TOOL_SPECS is {type(spec).__name__}, not FLToolSpec"
        )


def test_execution_modes_are_valid() -> None:
    for spec in FL_TOOL_SPECS:
        assert spec.execution_mode in _VALID_EXECUTION_MODES, (
            f"Spec {spec.name!r} has invalid execution_mode {spec.execution_mode!r}"
        )


def test_by_change_keys_match_spec_domain_operation_pairs() -> None:
    spec_pairs = {(spec.domain, spec.operation) for spec in FL_TOOL_SPECS}
    by_change_keys = set(FL_TOOL_BY_CHANGE.keys())
    assert by_change_keys == spec_pairs, (
        f"Mismatched domain/operation pairs: "
        f"extra={by_change_keys - spec_pairs}, "
        f"missing={spec_pairs - by_change_keys}"
    )


def test_all_response_models_are_pydantic_base_model_subclasses() -> None:
    for spec in FL_TOOL_SPECS:
        assert issubclass(spec.response_model, BaseModel), (
            f"Spec {spec.name!r} response_model {spec.response_model!r} is not a BaseModel subclass"
        )


def test_all_request_models_inherit_fl_tool_request() -> None:
    for spec in FL_TOOL_SPECS:
        assert issubclass(spec.request_model, FLToolRequest), (
            f"Spec {spec.name!r} request_model {spec.request_model!r} "
            f"does not inherit from FLToolRequest"
        )


def test_non_read_tools_have_read_only_hint_false() -> None:
    for spec in FL_TOOL_SPECS:
        if spec.execution_mode != "read":
            assert spec.annotations["readOnlyHint"] is False, (
                f"Non-read tool {spec.name!r} should have readOnlyHint=False, "
                f"got {spec.annotations['readOnlyHint']!r}"
            )


def test_all_descriptions_are_non_empty_strings() -> None:
    for spec in FL_TOOL_SPECS:
        assert isinstance(spec.description, str) and len(spec.description) > 0, (
            f"Spec {spec.name!r} has empty or non-string description"
        )


def test_handler_names_match_spec_names() -> None:
    handler_keys = set(FL_TOOL_HANDLERS.keys())
    spec_names = {spec.name for spec in FL_TOOL_SPECS}
    assert handler_keys == spec_names


def test_model_dump_returns_dict_for_every_spec() -> None:
    for spec in FL_TOOL_SPECS:
        dumped = spec.model_dump()
        assert isinstance(dumped, dict), (
            f"Spec {spec.name!r} model_dump() returned {type(dumped).__name__}"
        )
        assert dumped["name"] == spec.name
        assert dumped["domain"] == spec.domain
        assert dumped["operation"] == spec.operation


def test_capability_catalog_tools_count_matches_specs() -> None:
    catalog = capability_catalog()
    tools = catalog["tools"]
    assert isinstance(tools, list)
    assert len(tools) == len(FL_TOOL_SPECS)


def test_capability_catalog_domains_match_spec_domains() -> None:
    catalog = capability_catalog()
    catalog_domains = set(catalog["domains"])
    spec_domains = {spec.domain for spec in FL_TOOL_SPECS}
    assert catalog_domains == spec_domains
