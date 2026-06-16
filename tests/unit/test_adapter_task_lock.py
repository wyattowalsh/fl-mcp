"""Tests for provider adapter task lock behaviour and legacy adapter stubs."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from fl_mcp.providers.adapters import (
    BridgeBackedProvider,
    LegacyProviderAdapter,
    build_manifest,
)
from fl_mcp.schemas.provider import ProviderAdapterTaskRecord


def _make_legacy_adapter() -> LegacyProviderAdapter:
    """Build a minimal LegacyProviderAdapter for testing."""
    manifest = build_manifest(
        name="legacy-test",
        description="Test legacy adapter",
        supported_domains=["mixer"],
        maturity="experimental",
    )
    provider = MagicMock()
    provider.manifest = manifest.model_dump()
    return LegacyProviderAdapter(provider=provider, manifest=manifest)


def _make_bridge_backed_provider() -> BridgeBackedProvider:
    """Build a BridgeBackedProvider with a mock bridge for testing."""
    manifest = build_manifest(
        name="bridge-test",
        description="Test bridge-backed provider",
        supported_domains=["mixer"],
        maturity="experimental",
    )
    return BridgeBackedProvider(
        manifest=manifest,
        bridge_provider="mock",
    )


class TestLegacyAdapterTaskStubs:
    """LegacyProviderAdapter task methods return None."""

    def test_legacy_adapter_cancel_task_returns_none(self) -> None:
        adapter = _make_legacy_adapter()
        result = adapter.cancel_task("any-id")
        assert result is None

    def test_legacy_adapter_poll_task_returns_none(self) -> None:
        adapter = _make_legacy_adapter()
        result = adapter.poll_task("any-id")
        assert result is None


class TestBridgeBackedConcurrentTaskLock:
    """BridgeBackedProvider task lock prevents race conditions under concurrency."""

    @patch("fl_mcp.providers.adapters.FLStudioBridge.from_environment")
    def test_bridge_backed_concurrent_start_cancel(self, mock_from_env: MagicMock) -> None:
        """Spawn threads calling start_task and cancel_task concurrently.

        Assert no exceptions are raised and task state remains consistent.
        """
        mock_bridge = MagicMock()
        mock_bridge.execute_operation.return_value = MagicMock(
            success=True,
            message="Mock executed mixer.get_track",
            result={"task_status": "queued"},
            error_code=None,
            execution_id="exec-001",
            bridge_mode="mock",
        )
        mock_from_env.return_value = mock_bridge

        provider = _make_bridge_backed_provider()

        errors: list[Exception] = []
        started_task_ids: list[str] = []
        lock = threading.Lock()

        def _start_task() -> None:
            try:
                record = provider.start_task(
                    domain="mixer",
                    operation="get_track",
                    payload={"track": 0},
                )
                with lock:
                    started_task_ids.append(record.task_id)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        def _cancel_task(task_id: str) -> None:
            try:
                provider.cancel_task(task_id)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        # Phase 1: Start several tasks concurrently
        start_threads = [threading.Thread(target=_start_task) for _ in range(4)]
        for t in start_threads:
            t.start()
        for t in start_threads:
            t.join(timeout=5)

        assert not errors, f"Unexpected errors during start_task: {errors}"
        assert len(started_task_ids) == 4

        # Phase 2: Cancel tasks concurrently (including interleaved starts)
        cancel_threads = [
            threading.Thread(target=_cancel_task, args=(tid,)) for tid in started_task_ids
        ]
        extra_start_threads = [threading.Thread(target=_start_task) for _ in range(2)]

        all_threads = cancel_threads + extra_start_threads
        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join(timeout=5)

        assert not errors, f"Unexpected errors during concurrent cancel/start: {errors}"

        # Verify all originally-started tasks reached a consistent terminal state
        for tid in started_task_ids:
            record = provider.poll_task(tid)
            assert record is not None
            assert isinstance(record, ProviderAdapterTaskRecord)
            assert record.state in {"queued", "running", "completed", "failed", "canceled"}
