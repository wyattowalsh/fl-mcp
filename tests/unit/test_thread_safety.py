"""Thread-safety tests for global mutable singletons."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from fl_mcp.providers.runtime import (
    ProviderRegistry,
    get_provider_registry,
)
from fl_mcp.runtime.state import get_runtime_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _DummyProvider:
    manifest: dict[str, object]

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _make_dummy(name: str) -> _DummyProvider:
    return _DummyProvider(
        manifest={
            "name": name,
            "version": "0.1.0",
            "capabilities": ["diag"],
            "maturity": "beta",
        },
    )


# ---------------------------------------------------------------------------
# RuntimeState: concurrent render job creation
# ---------------------------------------------------------------------------


def test_concurrent_render_job_creation() -> None:
    state = get_runtime_state()

    def create_job(i: int) -> str:
        record = state.create_render_job(
            provider="mock",
            tool=f"tool_{i}",
            operation=f"op_{i}",
            payload={"index": i},
            result={"job_id": f"job-{i}", "task_status": "queued"},
        )
        return record.id

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(create_job, i) for i in range(50)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 50
    assert len(state.render_jobs) == 50
    # Every job id must be present in the dict
    assert set(results) == set(state.render_jobs.keys())


# ---------------------------------------------------------------------------
# RuntimeState: concurrent audio analysis creation
# ---------------------------------------------------------------------------


def test_concurrent_audio_analysis_creation() -> None:
    state = get_runtime_state()

    def create_analysis(i: int) -> str:
        record = state.create_audio_analysis(
            provider="mock",
            tool=f"analyze_{i}",
            operation=f"op_{i}",
            payload={"index": i},
            result={"analysis_id": f"analysis-{i}", "task_status": "running"},
        )
        return record.id

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(create_analysis, i) for i in range(50)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 50
    assert len(state.audio_analyses) == 50
    assert set(results) == set(state.audio_analyses.keys())


# ---------------------------------------------------------------------------
# RuntimeState: concurrent reads during writes
# ---------------------------------------------------------------------------


def test_concurrent_reads_during_writes() -> None:
    state = get_runtime_state()

    # Pre-populate some jobs so reads have something to return
    for i in range(10):
        state.create_render_job(
            provider="mock",
            tool=f"tool_{i}",
            operation=f"op_{i}",
            payload={"index": i},
            result={"job_id": f"seed-{i}", "task_status": "queued"},
        )

    errors: list[str] = []

    def writer(i: int) -> str:
        record = state.create_render_job(
            provider="mock",
            tool=f"tool_w{i}",
            operation=f"op_w{i}",
            payload={"index": i},
            result={"job_id": f"write-{i}", "task_status": "queued"},
        )
        return record.id

    def reader(i: int) -> str | None:
        # Read a pre-seeded job; snapshot must be consistent (not partial)
        record = state.get_render_job(f"seed-{i % 10}")
        if record is not None and record.id != f"seed-{i % 10}":
            errors.append(f"Inconsistent read: expected seed-{i % 10}, got {record.id}")
        return record.id if record else None

    with ThreadPoolExecutor(max_workers=12) as pool:
        write_futures = [pool.submit(writer, i) for i in range(30)]
        read_futures = [pool.submit(reader, i) for i in range(30)]
        all_futures = write_futures + read_futures
        _ = [f.result() for f in as_completed(all_futures)]

    assert not errors, f"Inconsistent reads detected: {errors}"
    # Original 10 seeds + 30 writes
    assert len(state.render_jobs) == 40


# ---------------------------------------------------------------------------
# RuntimeState: get_runtime_state singleton under contention
# ---------------------------------------------------------------------------


def test_get_runtime_state_singleton_under_contention() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_runtime_state) for _ in range(50)]
        instances = [f.result() for f in as_completed(futures)]

    # All threads must receive the exact same object
    assert all(inst is instances[0] for inst in instances)


# ---------------------------------------------------------------------------
# ProviderRegistry: concurrent registration
# ---------------------------------------------------------------------------


def test_concurrent_provider_registration() -> None:
    registry = ProviderRegistry()

    def register_provider(i: int) -> str:
        provider = _make_dummy(f"provider-{i}")
        manifest = registry.register(provider)
        return manifest.name

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(register_provider, i) for i in range(30)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 30
    manifests = registry.manifests()
    assert len(manifests) == 30
    registered_names = {m.name for m in manifests}
    assert registered_names == {f"provider-{i}" for i in range(30)}


# ---------------------------------------------------------------------------
# ProviderRegistry: get_provider_registry singleton under contention
# ---------------------------------------------------------------------------


def test_get_provider_registry_singleton_under_contention() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_provider_registry, load_entry_points=False) for _ in range(50)]
        instances = [f.result() for f in as_completed(futures)]

    assert all(inst is instances[0] for inst in instances)
