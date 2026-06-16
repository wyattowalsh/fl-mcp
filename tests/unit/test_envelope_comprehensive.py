"""Comprehensive validation tests for transaction envelopes and domain changes."""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from fl_mcp.schemas.transaction import (
    DomainChange,
    TransactionEnvelope,
)
from fl_mcp.transactions.envelope import validate_envelope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_change(**overrides: object) -> dict[str, object]:
    """Return a minimal valid DomainChange dict, with optional overrides."""
    base: dict[str, object] = {
        "domain": "mixer",
        "operation": "set_volume",
        "rollback_class": "checkpointed",
    }
    base.update(overrides)
    return base


def _minimal_envelope(**overrides: object) -> dict[str, object]:
    """Return a minimal valid TransactionEnvelope dict, with optional overrides."""
    base: dict[str, object] = {
        "request_id": "req-1",
        "mode": "apply",
        "changes": [_minimal_change()],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. TransactionEnvelope — execution_policy
# ---------------------------------------------------------------------------


class TestExecutionPolicy:
    """TransactionEnvelope with all valid execution_policy values."""

    @pytest.mark.parametrize("policy", ["all-or-nothing", "allow-partial"])
    def test_valid_execution_policies(self, policy: str) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(execution_policy=policy))
        assert env.execution_policy == policy

    def test_default_execution_policy_is_all_or_nothing(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.execution_policy == "all-or-nothing"

    def test_invalid_execution_policy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(_minimal_envelope(execution_policy="best-effort"))


# ---------------------------------------------------------------------------
# 2. TransactionEnvelope — safety_mode
# ---------------------------------------------------------------------------


class TestSafetyMode:
    """TransactionEnvelope with all valid safety_mode values."""

    @pytest.mark.parametrize("mode", ["strict", "standard", "relaxed"])
    def test_valid_safety_modes(self, mode: str) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(safety_mode=mode))
        assert env.safety_mode == mode

    def test_default_safety_mode_is_standard(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.safety_mode == "standard"

    def test_invalid_safety_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(_minimal_envelope(safety_mode="permissive"))


# ---------------------------------------------------------------------------
# 3. TransactionEnvelope — freshness_policy
# ---------------------------------------------------------------------------


class TestFreshnessPolicy:
    """TransactionEnvelope with all valid freshness_policy values."""

    @pytest.mark.parametrize("fp", ["strict", "allow-stale"])
    def test_valid_freshness_policies(self, fp: str) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(freshness_policy=fp))
        assert env.freshness_policy == fp

    def test_default_freshness_policy_is_strict(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.freshness_policy == "strict"

    def test_invalid_freshness_policy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(_minimal_envelope(freshness_policy="eventual"))


# ---------------------------------------------------------------------------
# 4. Envelope with varying change counts
# ---------------------------------------------------------------------------


class TestChangeCount:
    """Envelope with 1, 5, and 20 (bulk) changes."""

    def test_single_change(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=[_minimal_change()]))
        assert len(env.changes) == 1

    def test_five_changes(self) -> None:
        changes = [_minimal_change(domain=f"domain-{i}", operation=f"op-{i}") for i in range(5)]
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=changes))
        assert len(env.changes) == 5

    def test_twenty_changes_bulk(self) -> None:
        changes = [_minimal_change(domain=f"domain-{i}", operation=f"op-{i}") for i in range(20)]
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=changes))
        assert len(env.changes) == 20

    def test_empty_changes_list_accepted(self) -> None:
        """Pydantic does not enforce min length unless configured."""
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=[]))
        assert len(env.changes) == 0


# ---------------------------------------------------------------------------
# 5. Envelope mode: "preview" vs "apply"
# ---------------------------------------------------------------------------


class TestEnvelopeMode:
    """Envelope mode 'preview' vs 'apply'."""

    @pytest.mark.parametrize("mode", ["preview", "apply"])
    def test_valid_modes(self, mode: str) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(mode=mode))
        assert env.mode == mode

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(_minimal_envelope(mode="dry-run"))


# ---------------------------------------------------------------------------
# 6. DomainChange — rollback_class
# ---------------------------------------------------------------------------


class TestRollbackClass:
    """DomainChange with all valid rollback_class values."""

    @pytest.mark.parametrize(
        "rc",
        ["fully_transactional", "checkpointed", "best_effort", "unsafe_raw"],
    )
    def test_valid_rollback_classes(self, rc: str) -> None:
        change = DomainChange.model_validate(_minimal_change(rollback_class=rc))
        assert change.rollback_class == rc

    def test_invalid_rollback_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DomainChange.model_validate(_minimal_change(rollback_class="yolo"))


# ---------------------------------------------------------------------------
# 7. DomainChange — nested dict payload
# ---------------------------------------------------------------------------


class TestNestedPayload:
    """DomainChange with payload containing nested dicts."""

    def test_nested_dict_payload(self) -> None:
        payload = {
            "level1": {
                "level2": {
                    "value": 42,
                    "tags": ["a", "b"],
                }
            }
        }
        change = DomainChange.model_validate(_minimal_change(payload=payload))
        assert change.payload["level1"]["level2"]["value"] == 42  # type: ignore[index]

    def test_deeply_nested_dict_payload(self) -> None:
        payload: dict[str, object] = {"root": {"a": {"b": {"c": {"d": "deep"}}}}}
        change = DomainChange.model_validate(_minimal_change(payload=payload))
        inner = change.payload["root"]  # type: ignore[index]
        assert inner["a"]["b"]["c"]["d"] == "deep"  # type: ignore[index]


# ---------------------------------------------------------------------------
# 8. DomainChange — payload containing lists
# ---------------------------------------------------------------------------


class TestListPayload:
    """DomainChange with payload containing lists."""

    def test_list_payload(self) -> None:
        payload = {"steps": [0, 4, 8, 12], "labels": ["kick", "snare"]}
        change = DomainChange.model_validate(_minimal_change(payload=payload))
        assert change.payload["steps"] == [0, 4, 8, 12]
        assert change.payload["labels"] == ["kick", "snare"]

    def test_list_of_dicts_payload(self) -> None:
        payload = {"notes": [{"pitch": 60, "vel": 100}, {"pitch": 64, "vel": 80}]}
        change = DomainChange.model_validate(_minimal_change(payload=payload))
        assert len(change.payload["notes"]) == 2  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 9. DomainChange — empty payload
# ---------------------------------------------------------------------------


class TestEmptyPayload:
    """DomainChange with empty payload."""

    def test_explicit_empty_payload(self) -> None:
        change = DomainChange.model_validate(_minimal_change(payload={}))
        assert change.payload == {}

    def test_default_payload_is_empty_dict(self) -> None:
        raw = {"domain": "mixer", "operation": "noop", "rollback_class": "best_effort"}
        change = DomainChange.model_validate(raw)
        assert change.payload == {}


# ---------------------------------------------------------------------------
# 10. DomainChange — None provider (auto-resolve)
# ---------------------------------------------------------------------------


class TestProviderNone:
    """DomainChange with None provider triggers auto-resolve."""

    def test_explicit_none_provider(self) -> None:
        change = DomainChange.model_validate(_minimal_change(provider=None))
        assert change.provider is None

    def test_omitted_provider_defaults_to_none(self) -> None:
        raw = {"domain": "mixer", "operation": "noop", "rollback_class": "best_effort"}
        change = DomainChange.model_validate(raw)
        assert change.provider is None


# ---------------------------------------------------------------------------
# 11. DomainChange — explicit provider
# ---------------------------------------------------------------------------


class TestExplicitProvider:
    """DomainChange with explicit provider."""

    def test_explicit_provider_accepted(self) -> None:
        change = DomainChange.model_validate(_minimal_change(provider="flapi-live"))
        assert change.provider == "flapi-live"

    def test_provider_arbitrary_string(self) -> None:
        change = DomainChange.model_validate(_minimal_change(provider="custom-bridge-v2"))
        assert change.provider == "custom-bridge-v2"


# ---------------------------------------------------------------------------
# 12. validate_envelope() with valid envelope dict
# ---------------------------------------------------------------------------


class TestValidateEnvelopeValid:
    """validate_envelope() from envelope.py with valid envelope dict."""

    def test_minimal_valid_envelope(self) -> None:
        assert validate_envelope(_minimal_envelope()) is True

    def test_fully_specified_valid_envelope(self) -> None:
        data = _minimal_envelope(
            execution_policy="allow-partial",
            safety_mode="relaxed",
            freshness_policy="allow-stale",
            target_snapshot_id="snap-abc",
            preconditions=["project_saved"],
            metadata={"author": "test"},
        )
        assert validate_envelope(data) is True


# ---------------------------------------------------------------------------
# 13. validate_envelope() with missing required fields
# ---------------------------------------------------------------------------


class TestValidateEnvelopeMissingFields:
    """validate_envelope() with missing required fields."""

    def test_missing_request_id(self) -> None:
        data = _minimal_envelope()
        del data["request_id"]  # type: ignore[arg-type]
        assert validate_envelope(data) is False

    def test_missing_mode(self) -> None:
        data = _minimal_envelope()
        del data["mode"]  # type: ignore[arg-type]
        assert validate_envelope(data) is False

    def test_missing_changes(self) -> None:
        data = _minimal_envelope()
        del data["changes"]  # type: ignore[arg-type]
        assert validate_envelope(data) is False

    def test_empty_dict(self) -> None:
        assert validate_envelope({}) is False


# ---------------------------------------------------------------------------
# 14. validate_envelope() with invalid types
# ---------------------------------------------------------------------------


class TestValidateEnvelopeInvalidTypes:
    """validate_envelope() with invalid types."""

    def test_request_id_as_int(self) -> None:
        assert validate_envelope(_minimal_envelope(request_id=42)) is False

    def test_mode_as_int(self) -> None:
        assert validate_envelope(_minimal_envelope(mode=123)) is False

    def test_changes_as_string(self) -> None:
        assert validate_envelope(_minimal_envelope(changes="not-a-list")) is False

    def test_changes_item_as_string(self) -> None:
        assert validate_envelope(_minimal_envelope(changes=["not-a-dict"])) is False

    def test_execution_policy_invalid_literal(self) -> None:
        assert validate_envelope(_minimal_envelope(execution_policy="invalid")) is False


# ---------------------------------------------------------------------------
# 15. Serialization roundtrip: construct -> model_dump -> model_validate
# ---------------------------------------------------------------------------


class TestModelDumpRoundtrip:
    """Envelope serialization roundtrip via model_dump / model_validate."""

    def test_roundtrip_preserves_all_fields(self) -> None:
        original = TransactionEnvelope.model_validate(
            _minimal_envelope(
                request_id="rt-1",
                mode="preview",
                execution_policy="allow-partial",
                safety_mode="relaxed",
                freshness_policy="allow-stale",
                target_snapshot_id="snap-0",
                preconditions=["cond-a"],
                metadata={"k": "v"},
                changes=[
                    _minimal_change(domain="mixer", payload={"vol": 0.8}),
                    _minimal_change(domain="transport", operation="play"),
                ],
            )
        )
        dumped = original.model_dump()
        restored = TransactionEnvelope.model_validate(dumped)

        assert restored.request_id == original.request_id
        assert restored.mode == original.mode
        assert restored.execution_policy == original.execution_policy
        assert restored.safety_mode == original.safety_mode
        assert restored.freshness_policy == original.freshness_policy
        assert restored.target_snapshot_id == original.target_snapshot_id
        assert restored.preconditions == original.preconditions
        assert restored.metadata == original.metadata
        assert len(restored.changes) == len(original.changes)
        for orig_c, rest_c in zip(original.changes, restored.changes, strict=True):
            assert rest_c.domain == orig_c.domain
            assert rest_c.operation == orig_c.operation
            assert rest_c.rollback_class == orig_c.rollback_class
            assert rest_c.provider == orig_c.provider
            assert rest_c.payload == orig_c.payload

    def test_change_roundtrip(self) -> None:
        original = DomainChange.model_validate(
            _minimal_change(provider="flapi-live", payload={"bpm": 120})
        )
        restored = DomainChange.model_validate(original.model_dump())
        assert restored == original


# ---------------------------------------------------------------------------
# 16. JSON roundtrip: construct -> model_dump_json -> model_validate_json
# ---------------------------------------------------------------------------


class TestJsonRoundtrip:
    """Envelope JSON roundtrip via model_dump_json / model_validate_json."""

    def test_json_roundtrip_preserves_all_fields(self) -> None:
        original = TransactionEnvelope.model_validate(
            _minimal_envelope(
                request_id="json-rt-1",
                mode="apply",
                execution_policy="all-or-nothing",
                safety_mode="strict",
                freshness_policy="strict",
                changes=[
                    _minimal_change(
                        payload={"nested": {"key": [1, 2, 3]}},
                        provider="flapi-live",
                    )
                ],
            )
        )
        json_str = original.model_dump_json()
        restored = TransactionEnvelope.model_validate_json(json_str)

        assert restored == original

    def test_json_is_valid_json(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        parsed = json.loads(env.model_dump_json())
        assert isinstance(parsed, dict)
        assert "request_id" in parsed

    def test_change_json_roundtrip(self) -> None:
        original = DomainChange.model_validate(
            _minimal_change(provider="midi-fallback", payload={"steps": [0, 4]})
        )
        restored = DomainChange.model_validate_json(original.model_dump_json())
        assert restored == original


# ---------------------------------------------------------------------------
# 17. Change ordering preservation in envelope
# ---------------------------------------------------------------------------


class TestChangeOrdering:
    """Change ordering preservation in envelope."""

    def test_change_order_preserved(self) -> None:
        domains = [f"domain-{i}" for i in range(10)]
        changes = [_minimal_change(domain=d) for d in domains]
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=changes))
        assert [c.domain for c in env.changes] == domains

    def test_order_preserved_through_dump_roundtrip(self) -> None:
        operations = [f"op-{i}" for i in range(7)]
        changes = [_minimal_change(operation=op) for op in operations]
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=changes))
        dumped = env.model_dump()
        restored = TransactionEnvelope.model_validate(dumped)
        assert [c.operation for c in restored.changes] == operations

    def test_order_preserved_through_json_roundtrip(self) -> None:
        operations = [f"op-{i}" for i in range(7)]
        changes = [_minimal_change(operation=op) for op in operations]
        env = TransactionEnvelope.model_validate(_minimal_envelope(changes=changes))
        restored = TransactionEnvelope.model_validate_json(env.model_dump_json())
        assert [c.operation for c in restored.changes] == operations


# ---------------------------------------------------------------------------
# 18. Request ID uniqueness enforcement
# ---------------------------------------------------------------------------


class TestRequestIdUniqueness:
    """Request ID uniqueness — schema-level behaviour (no enforcement)."""

    def test_duplicate_request_ids_both_valid_at_schema_level(self) -> None:
        """The schema itself does not enforce cross-envelope uniqueness."""
        env_a = TransactionEnvelope.model_validate(_minimal_envelope(request_id="dup-1"))
        env_b = TransactionEnvelope.model_validate(_minimal_envelope(request_id="dup-1"))
        assert env_a.request_id == env_b.request_id

    def test_uuid_request_ids_are_unique(self) -> None:
        """Demonstrate practical uniqueness via UUIDs."""
        ids = {
            TransactionEnvelope.model_validate(
                _minimal_envelope(request_id=str(uuid.uuid4()))
            ).request_id
            for _ in range(50)
        }
        assert len(ids) == 50

    def test_request_id_is_required_string(self) -> None:
        with pytest.raises(ValidationError):
            TransactionEnvelope.model_validate(_minimal_envelope(request_id=None))


# ---------------------------------------------------------------------------
# Additional edge-case coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Miscellaneous edge cases for schema robustness."""

    def test_schema_version_default(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.schema_version == "1.0"

    def test_schema_version_override(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope(schema_version="2.0"))
        assert env.schema_version == "2.0"

    def test_target_snapshot_id_defaults_to_none(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.target_snapshot_id is None

    def test_preconditions_default_to_empty(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.preconditions == []

    def test_metadata_default_to_empty(self) -> None:
        env = TransactionEnvelope.model_validate(_minimal_envelope())
        assert env.metadata == {}

    def test_domain_change_equality(self) -> None:
        a = DomainChange.model_validate(_minimal_change())
        b = DomainChange.model_validate(_minimal_change())
        assert a == b

    def test_validate_envelope_returns_bool(self) -> None:
        result = validate_envelope(_minimal_envelope())
        assert isinstance(result, bool)
