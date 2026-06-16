"""Edge-case tests for planner, apply, and domain_result_key not covered by happy-path suite."""

from __future__ import annotations

from collections import Counter, defaultdict

from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.transactions.apply import apply_changes
from fl_mcp.transactions.interfaces import domain_result_key
from fl_mcp.transactions.planner import plan_changes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _envelope(
    *,
    changes: list[dict[str, object]],
    mode: str = "apply",
    execution_policy: str = "all-or-nothing",
    request_id: str = "edge-1",
    target_snapshot_id: str | None = "snap-before",
) -> TransactionEnvelope:
    return TransactionEnvelope.model_validate(
        {
            "request_id": request_id,
            "mode": mode,
            "execution_policy": execution_policy,
            "target_snapshot_id": target_snapshot_id,
            "changes": changes,
        }
    )


def _change(
    domain: str = "transport",
    operation: str = "set_tempo",
    rollback_class: str = "checkpointed",
    **extra: object,
) -> dict[str, object]:
    if "payload" not in extra and domain == "transport" and operation == "set_tempo":
        extra["payload"] = {"bpm": 120.0}
    return {"domain": domain, "operation": operation, "rollback_class": rollback_class, **extra}


# ---------------------------------------------------------------------------
# 1. Empty envelope — plan_changes returns planned result with warning
# ---------------------------------------------------------------------------


class TestEmptyEnvelope:
    def test_plan_changes_empty_returns_planned_with_warning(self) -> None:
        envelope = _envelope(changes=[], mode="preview")
        result = plan_changes(envelope)

        assert result.status == "planned"
        assert result.per_domain_results == {}
        assert result.diff_summary["change_count"] == 0
        assert any("No changes" in w for w in result.warnings)

    def test_plan_changes_empty_transaction_id_contains_request_id(self) -> None:
        envelope = _envelope(changes=[], mode="preview", request_id="empty-req")
        result = plan_changes(envelope)

        assert "empty-req" in result.transaction_id

    def test_plan_changes_empty_snapshot_passthrough(self) -> None:
        envelope = _envelope(changes=[], mode="preview", target_snapshot_id="snap-x")
        result = plan_changes(envelope)

        assert result.snapshot_before == "snap-x"
        assert result.snapshot_after == "snap-x"


# ---------------------------------------------------------------------------
# 2. Single change — plan and apply, key is plain domain name
# ---------------------------------------------------------------------------


class TestSingleChange:
    def test_plan_single_change_key_is_plain_domain(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="transport", operation="set_tempo")],
            mode="preview",
        )
        result = plan_changes(envelope)

        assert "transport" in result.per_domain_results
        # No suffixed keys
        assert not any("#" in k for k in result.per_domain_results)
        assert result.per_domain_results["transport"] == "planned"

    def test_apply_single_change_key_is_plain_domain(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="transport", operation="set_tempo")],
            mode="apply",
        )
        result = apply_changes(envelope)

        assert "transport" in result.per_domain_results
        assert not any("#" in k for k in result.per_domain_results)
        assert result.per_domain_results["transport"] == "applied"

    def test_apply_single_change_produces_checkpoint(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="mixer", operation="set_volume")],
            mode="apply",
        )
        result = apply_changes(envelope)

        assert result.status == "applied"
        assert result.checkpoint_id is not None


# ---------------------------------------------------------------------------
# 3. Multiple changes same domain — keys get hash-suffixed
# ---------------------------------------------------------------------------


class TestMultipleChangesSameDomain:
    def test_plan_duplicate_domain_produces_suffixed_keys(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume"),
                _change(domain="mixer", operation="set_pan"),
            ],
            mode="preview",
        )
        result = plan_changes(envelope)

        assert "mixer#1" in result.per_domain_results
        assert "mixer#2" in result.per_domain_results
        assert len(result.per_domain_results) == 2

    def test_apply_duplicate_domain_produces_suffixed_keys(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume"),
                _change(domain="mixer", operation="set_pan"),
            ],
            mode="apply",
        )
        result = apply_changes(envelope)

        assert "mixer#1" in result.per_domain_results
        assert "mixer#2" in result.per_domain_results

    def test_plan_three_same_domain_produces_three_suffixed_keys(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume"),
                _change(domain="mixer", operation="set_pan"),
                _change(domain="mixer", operation="set_name"),
            ],
            mode="preview",
        )
        result = plan_changes(envelope)

        assert "mixer#1" in result.per_domain_results
        assert "mixer#2" in result.per_domain_results
        assert "mixer#3" in result.per_domain_results
        assert len(result.per_domain_results) == 3

    def test_mixed_domains_only_duplicates_get_suffixed(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume"),
                _change(domain="mixer", operation="set_pan"),
                _change(domain="transport", operation="set_tempo"),
            ],
            mode="preview",
        )
        result = plan_changes(envelope)

        assert "mixer#1" in result.per_domain_results
        assert "mixer#2" in result.per_domain_results
        assert "transport" in result.per_domain_results
        assert len(result.per_domain_results) == 3


# ---------------------------------------------------------------------------
# 4. domain_result_key() direct unit tests
# ---------------------------------------------------------------------------


class TestDomainResultKeyHelper:
    @staticmethod
    def _make_change(domain: str) -> DomainChange:
        return DomainChange(
            domain=domain,
            operation="noop",
            rollback_class="best_effort",
        )

    def test_single_domain_returns_plain_name(self) -> None:
        totals: Counter[str] = Counter({"transport": 1})
        seen: defaultdict[str, int] = defaultdict(int)
        change = self._make_change("transport")

        key = domain_result_key(change, totals, seen)

        assert key == "transport"

    def test_two_same_domain_returns_suffixed_keys(self) -> None:
        totals: Counter[str] = Counter({"mixer": 2})
        seen: defaultdict[str, int] = defaultdict(int)

        key1 = domain_result_key(self._make_change("mixer"), totals, seen)
        key2 = domain_result_key(self._make_change("mixer"), totals, seen)

        assert key1 == "mixer#1"
        assert key2 == "mixer#2"

    def test_three_same_domain_increments_monotonically(self) -> None:
        totals: Counter[str] = Counter({"patterns": 3})
        seen: defaultdict[str, int] = defaultdict(int)

        keys = [domain_result_key(self._make_change("patterns"), totals, seen) for _ in range(3)]

        assert keys == ["patterns#1", "patterns#2", "patterns#3"]

    def test_different_domains_each_get_plain_name(self) -> None:
        totals: Counter[str] = Counter({"mixer": 1, "transport": 1, "channels": 1})
        seen: defaultdict[str, int] = defaultdict(int)

        keys = [
            domain_result_key(self._make_change(d), totals, seen)
            for d in ("mixer", "transport", "channels")
        ]

        assert keys == ["mixer", "transport", "channels"]

    def test_mixed_single_and_multi(self) -> None:
        totals: Counter[str] = Counter({"mixer": 2, "transport": 1})
        seen: defaultdict[str, int] = defaultdict(int)

        k1 = domain_result_key(self._make_change("mixer"), totals, seen)
        k2 = domain_result_key(self._make_change("transport"), totals, seen)
        k3 = domain_result_key(self._make_change("mixer"), totals, seen)

        assert k1 == "mixer#1"
        assert k2 == "transport"
        assert k3 == "mixer#2"

    def test_seen_state_is_mutated_in_place(self) -> None:
        totals: Counter[str] = Counter({"mixer": 2})
        seen: defaultdict[str, int] = defaultdict(int)

        domain_result_key(self._make_change("mixer"), totals, seen)

        assert seen["mixer"] == 1

        domain_result_key(self._make_change("mixer"), totals, seen)

        assert seen["mixer"] == 2


# ---------------------------------------------------------------------------
# 5. Apply in preview mode — returns planned without executing
# ---------------------------------------------------------------------------


class TestApplyPreviewMode:
    def test_apply_preview_returns_planned_status(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="mixer", operation="set_volume")],
            mode="preview",
        )
        result = apply_changes(envelope)

        assert result.status == "planned"

    def test_apply_preview_diff_has_zero_applied(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="mixer", operation="set_volume")],
            mode="preview",
        )
        result = apply_changes(envelope)

        assert result.diff_summary["applied_count"] == 0
        assert result.diff_summary["failed_count"] == 0
        assert result.diff_summary["mode"] == "preview"

    def test_apply_preview_no_checkpoint(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="mixer", operation="set_volume")],
            mode="preview",
        )
        result = apply_changes(envelope)

        assert result.checkpoint_id is None

    def test_apply_preview_snapshot_unchanged(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="mixer", operation="set_volume")],
            mode="preview",
            target_snapshot_id="snap-orig",
        )
        result = apply_changes(envelope)

        assert result.snapshot_before == "snap-orig"
        assert result.snapshot_after == "snap-orig"

    def test_apply_preview_per_domain_all_planned(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume"),
                _change(domain="transport", operation="set_tempo"),
            ],
            mode="preview",
        )
        result = apply_changes(envelope)

        assert all(v == "planned" for v in result.per_domain_results.values())


# ---------------------------------------------------------------------------
# 6. Unknown domain in change — apply returns error for that domain
# ---------------------------------------------------------------------------


class TestUnknownDomain:
    def test_apply_unknown_domain_fails(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="nonexistent", operation="noop", rollback_class="unsafe_raw")],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.status == "failed"
        assert result.per_domain_results["nonexistent"] == "failed_checkpoint_required"

    def test_apply_unknown_domain_error_code_in_report(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="nonexistent", operation="noop", rollback_class="unsafe_raw")],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        reports = result.diff_summary["reports"]
        assert isinstance(reports, list)
        assert len(reports) == 1
        assert reports[0]["error_code"] == "unsupported_domain"

    def test_apply_unknown_domain_no_checkpoint_created(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="nonexistent", operation="noop", rollback_class="unsafe_raw")],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.checkpoint_id is None

    def test_apply_unknown_domain_snapshot_unchanged(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="nonexistent", operation="noop", rollback_class="unsafe_raw")],
            mode="apply",
            execution_policy="allow-partial",
            target_snapshot_id="snap-orig",
        )
        result = apply_changes(envelope)

        assert result.snapshot_after == "snap-orig"

    def test_apply_unknown_domain_errors_list_populated(self) -> None:
        envelope = _envelope(
            changes=[_change(domain="nonexistent", operation="noop", rollback_class="unsafe_raw")],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# 7. Mixed success/failure with allow-partial
# ---------------------------------------------------------------------------


class TestMixedSuccessFailureAllowPartial:
    def test_partially_applied_status(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.status == "partially_applied"

    def test_partially_applied_counts(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.diff_summary["applied_count"] == 1
        assert result.diff_summary["failed_count"] == 1

    def test_partially_applied_per_domain_results_differ(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.per_domain_results["mixer#1"] == "applied"
        assert result.per_domain_results["mixer#2"] == "failed_manual_intervention"

    def test_partially_applied_produces_warning(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert any("allow-partial" in w for w in result.warnings)

    def test_partially_applied_creates_checkpoint(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.checkpoint_id is not None

    def test_partially_applied_snapshot_advances(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
            target_snapshot_id="snap-old",
        )
        result = apply_changes(envelope)

        assert result.snapshot_after != "snap-old"

    def test_partially_applied_errors_contain_failure_message(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(domain="mixer", operation="fail_volume", rollback_class="best_effort"),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert len(result.errors) >= 1

    def test_mixed_across_different_domains(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="transport", operation="set_tempo", rollback_class="checkpointed"),
                _change(
                    domain="nonexistent",
                    operation="noop",
                    rollback_class="unsafe_raw",
                ),
            ],
            mode="apply",
            execution_policy="allow-partial",
        )
        result = apply_changes(envelope)

        assert result.status == "partially_applied"
        assert result.per_domain_results["transport"] == "applied"
        assert result.per_domain_results["nonexistent"] == "failed_checkpoint_required"

    def test_all_or_nothing_reverts_successful_on_any_failure(self) -> None:
        envelope = _envelope(
            changes=[
                _change(domain="mixer", operation="set_volume", rollback_class="checkpointed"),
                _change(
                    domain="transport",
                    operation="fail_start",
                    rollback_class="fully_transactional",
                ),
            ],
            mode="apply",
            execution_policy="all-or-nothing",
        )
        result = apply_changes(envelope)

        assert result.status == "failed"
        assert result.diff_summary["applied_count"] == 0
        assert result.diff_summary["failed_count"] == 2
        assert result.checkpoint_id is None
        assert "applied" not in set(result.per_domain_results.values())
