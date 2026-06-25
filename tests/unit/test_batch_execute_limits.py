"""Unit tests for fl_batch_execute size and live-mutation limits."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from fl_mcp.tools import compact


@pytest.fixture(autouse=True)
def _reset_live_mutation_counter() -> None:
    compact.reset_live_mutation_count()


def _mock_operation(operation_id: str) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "request": {"bpm": 120.0} if operation_id == "transport.set_tempo" else {"track_index": 0},
        "provider": "mock",
    }


def test_batch_execute_rejects_batches_over_max_size() -> None:
    over_limit = compact.MAX_BATCH_OPERATIONS + 1
    operations = [_mock_operation("transport.set_tempo") for _ in range(over_limit)]
    result = compact.fl_batch_execute(operations)

    assert result["status"] == "error"
    assert result["succeeded"] == 0
    assert result["total"] == compact.MAX_BATCH_OPERATIONS + 1
    assert "maximum size" in str(result["error"]).lower()


def test_batch_execute_allows_max_size_batch() -> None:
    operations = [
        _mock_operation("transport.get_tempo") for _ in range(compact.MAX_BATCH_OPERATIONS)
    ]
    result = compact.fl_batch_execute(operations)

    assert result["status"] == "ok"
    assert result["total"] == compact.MAX_BATCH_OPERATIONS


def test_batch_execute_rejects_live_mutations_over_session_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **kwargs: object) -> object:
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="live",
                execution_id="live-limit-test",
                message="ok",
                error_code=None,
                result={
                    "operation_id": f"{kwargs['domain']}.{kwargs['operation']}",
                    "payload": kwargs["payload"],
                },
            )

    monkeypatch.setattr(
        compact,
        "get_provider_registry",
        lambda load_entry_points=False: Registry(),
    )
    monkeypatch.setattr(compact, "MAX_LIVE_MUTATIONS_PER_SESSION", 2)
    compact.reset_live_mutation_count()

    live_operation = {
        "operation_id": "transport.set_tempo",
        "request": {"bpm": 128.0},
        "provider": "flapi-live",
    }
    first = compact.fl_batch_execute(
        [live_operation, live_operation],
        policy="continue-on-error",
    )
    assert first["status"] == "ok"
    assert compact.get_live_mutation_count() == 2

    second = compact.fl_batch_execute([live_operation])
    assert second["status"] == "error"
    assert "live mutation session limit" in str(second["error"]).lower()
    assert second["succeeded"] == 0


def test_batch_execute_mock_mutations_do_not_count_toward_live_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compact, "MAX_LIVE_MUTATIONS_PER_SESSION", 1)
    compact.reset_live_mutation_count()

    result = compact.fl_batch_execute(
        [
            _mock_operation("transport.set_tempo"),
            _mock_operation("transport.set_tempo"),
        ]
    )

    assert result["status"] == "ok"
    assert compact.get_live_mutation_count() == 0


def test_batch_execute_counts_only_non_read_only_live_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **kwargs: object) -> object:
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="live",
                execution_id="live-batch-test",
                message="ok",
                error_code=None,
                result={
                    "operation_id": f"{kwargs['domain']}.{kwargs['operation']}",
                    "payload": kwargs["payload"],
                },
            )

    monkeypatch.setattr(compact.DEFAULT_BRIDGE, "mode", "live")
    monkeypatch.setattr(
        compact,
        "get_provider_registry",
        lambda load_entry_points=False: Registry(),
    )
    monkeypatch.setattr(compact, "MAX_LIVE_MUTATIONS_PER_SESSION", 1)
    compact.reset_live_mutation_count()

    result = compact.fl_batch_execute(
        [
            {
                "operation_id": "transport.get_tempo",
                "request": {},
                "provider": "flapi-live",
            },
            {
                "operation_id": "transport.set_tempo",
                "request": {"bpm": 130.0},
                "provider": "flapi-live",
            },
        ]
    )

    assert result["status"] == "ok"
    assert compact.get_live_mutation_count() == 1


def test_fl_execute_enforces_live_mutation_session_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **kwargs: object) -> object:
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="live",
                execution_id="live-fl-execute-limit",
                message="ok",
                error_code=None,
                result={
                    "operation_id": f"{kwargs['domain']}.{kwargs['operation']}",
                    "payload": kwargs["payload"],
                },
            )

    monkeypatch.setattr(
        compact,
        "get_provider_registry",
        lambda load_entry_points=False: Registry(),
    )
    monkeypatch.setattr(compact, "MAX_LIVE_MUTATIONS_PER_SESSION", 1)
    compact.reset_live_mutation_count()

    live_operation = {
        "operation_id": "transport.set_tempo",
        "request": {"bpm": 128.0},
        "provider": "flapi-live",
    }
    first = compact.fl_execute(**live_operation)
    assert first["status"] == "ok"
    assert compact.get_live_mutation_count() == 1

    second = compact.fl_execute(**live_operation)
    assert second["status"] == "error"
    assert "live mutation session limit" in str(second["error"]).lower()
    assert compact.get_live_mutation_count() == 1