"""Concurrency stress tests for all thread-safe singletons in fl-mcp.

Validates that every guarded singleton returns the same instance under
high contention, and that concurrent mutations (render-job creation,
provider registration, graph snapshot/replace) do not crash or corrupt
shared state.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from unittest.mock import patch

from fl_mcp.graph.model import GraphNode, ProjectGraph
from fl_mcp.providers.runtime import (
    ProviderRegistry,
    get_provider_registry,
)
from fl_mcp.runtime.state import get_runtime_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STRESS_THREADS = 50
MEDIUM_THREADS = 20
MIXED_THREADS = 10


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
# 1. get_runtime_state() — 50 threads, all get same instance
# ---------------------------------------------------------------------------


def test_stress_get_runtime_state_singleton() -> None:
    """50 threads calling get_runtime_state() simultaneously must all receive
    the exact same RuntimeState instance."""
    with ThreadPoolExecutor(max_workers=STRESS_THREADS) as pool:
        futures = [pool.submit(get_runtime_state) for _ in range(STRESS_THREADS)]
        instances = [f.result() for f in as_completed(futures)]

    assert len(instances) == STRESS_THREADS
    first = instances[0]
    assert all(inst is first for inst in instances), (
        "get_runtime_state() returned different instances under contention"
    )


# ---------------------------------------------------------------------------
# 2. get_provider_registry() — 50 threads, all get same instance
# ---------------------------------------------------------------------------


def test_stress_get_provider_registry_singleton() -> None:
    """50 threads calling get_provider_registry() simultaneously must all
    receive the exact same ProviderRegistry instance."""
    with ThreadPoolExecutor(max_workers=STRESS_THREADS) as pool:
        futures = [
            pool.submit(get_provider_registry, load_entry_points=False)
            for _ in range(STRESS_THREADS)
        ]
        instances = [f.result() for f in as_completed(futures)]

    assert len(instances) == STRESS_THREADS
    first = instances[0]
    assert all(inst is first for inst in instances), (
        "get_provider_registry() returned different instances under contention"
    )


# ---------------------------------------------------------------------------
# 3. get_engine() — 50 threads, all get same instance
# ---------------------------------------------------------------------------


def test_stress_get_engine_singleton() -> None:
    """50 threads calling get_engine() simultaneously must all receive the
    exact same SQLAlchemy Engine instance."""
    import fl_mcp.persistence.db as db_mod

    # Reset the module-level singleton so the test starts clean.
    with db_mod._ENGINE_LOCK:
        db_mod._ENGINE = None

    try:
        with ThreadPoolExecutor(max_workers=STRESS_THREADS) as pool:
            futures = [pool.submit(db_mod.get_engine) for _ in range(STRESS_THREADS)]
            instances = [f.result() for f in as_completed(futures)]

        assert len(instances) == STRESS_THREADS
        first = instances[0]
        assert all(inst is first for inst in instances), (
            "get_engine() returned different instances under contention"
        )
    finally:
        # Clean up: dispose the engine and reset so other tests are unaffected.
        engine = db_mod._ENGINE
        with db_mod._ENGINE_LOCK:
            db_mod._ENGINE = None
        if engine is not None:
            engine.dispose()


# ---------------------------------------------------------------------------
# 4. 20 threads creating render jobs concurrently — no crashes, all created
# ---------------------------------------------------------------------------


def test_stress_concurrent_render_job_creation() -> None:
    """20 threads creating render jobs simultaneously must succeed without
    crashes, and every submitted job must be present in the state."""
    state = get_runtime_state()

    def create_job(i: int) -> str:
        record = state.create_render_job(
            provider="stress-mock",
            tool=f"stress_tool_{i}",
            operation=f"stress_op_{i}",
            payload={"thread_index": i},
            result={"job_id": f"stress-job-{i}", "task_status": "queued"},
        )
        return record.id

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        futures = [pool.submit(create_job, i) for i in range(MEDIUM_THREADS)]
        ids = [f.result() for f in as_completed(futures)]

    assert len(ids) == MEDIUM_THREADS
    assert len(state.render_jobs) == MEDIUM_THREADS
    assert set(ids) == set(state.render_jobs.keys())


# ---------------------------------------------------------------------------
# 5. 20 threads registering providers concurrently — no crashes
# ---------------------------------------------------------------------------


def test_stress_concurrent_provider_registration() -> None:
    """20 threads registering unique providers concurrently must not crash,
    and all providers must appear in the registry afterwards."""
    registry = ProviderRegistry()

    def register(i: int) -> str:
        provider = _make_dummy(f"stress-provider-{i}")
        manifest = registry.register(provider)
        return manifest.name

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        futures = [pool.submit(register, i) for i in range(MEDIUM_THREADS)]
        names = [f.result() for f in as_completed(futures)]

    assert len(names) == MEDIUM_THREADS
    manifests = registry.manifests()
    assert len(manifests) == MEDIUM_THREADS
    assert {m.name for m in manifests} == {f"stress-provider-{i}" for i in range(MEDIUM_THREADS)}


# ---------------------------------------------------------------------------
# 6. 10 snapshot_graph() + 10 replace_graph() concurrently — no crashes
# ---------------------------------------------------------------------------


def test_stress_snapshot_while_replace_graph() -> None:
    """10 threads snapshotting the graph while 10 threads replace it
    concurrently must not crash or produce partial/corrupt graphs."""
    state = get_runtime_state()
    errors: list[str] = []

    def do_replace(i: int) -> None:
        new_graph = ProjectGraph(
            nodes=[GraphNode(id=f"node-{i}", kind="test", data={"i": i})],
        )
        state.replace_graph(new_graph)

    def do_snapshot(_i: int) -> None:
        graph = state.snapshot_graph()
        # The snapshot must be a valid ProjectGraph — not half-written.
        if not isinstance(graph, ProjectGraph):
            errors.append(f"snapshot returned non-ProjectGraph: {type(graph)}")
        if graph.schema_version != "1.0":
            errors.append(f"snapshot has wrong schema_version: {graph.schema_version}")

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        snapshot_futures = [pool.submit(do_snapshot, i) for i in range(MIXED_THREADS)]
        replace_futures = [pool.submit(do_replace, i) for i in range(MIXED_THREADS)]
        all_futures = snapshot_futures + replace_futures
        for f in as_completed(all_futures):
            f.result()  # propagate exceptions

    assert not errors, f"Concurrent snapshot/replace errors: {errors}"


# ---------------------------------------------------------------------------
# 7. Mixed workload: get_runtime_state + snapshot + replace in a loop
# ---------------------------------------------------------------------------


def test_stress_mixed_runtime_state_workload() -> None:
    """10 threads each performing get_runtime_state(), snapshot_graph(), and
    replace_graph() in a tight loop must not crash or deadlock."""
    iterations = 20
    errors: list[str] = []
    barrier = threading.Barrier(MIXED_THREADS)

    def mixed_work(thread_id: int) -> None:
        barrier.wait(timeout=5)  # synchronize start
        for j in range(iterations):
            try:
                s = get_runtime_state()
                _ = s.snapshot_graph()
                new_g = ProjectGraph(
                    nodes=[
                        GraphNode(
                            id=f"mixed-{thread_id}-{j}",
                            kind="mixed",
                            data={"t": thread_id, "j": j},
                        )
                    ],
                )
                s.replace_graph(new_g)
            except Exception as exc:
                errors.append(f"thread-{thread_id} iter-{j}: {exc}")

    with ThreadPoolExecutor(max_workers=MIXED_THREADS) as pool:
        futures = [pool.submit(mixed_work, t) for t in range(MIXED_THREADS)]
        for f in as_completed(futures):
            f.result()

    assert not errors, f"Mixed workload errors: {errors}"


# ---------------------------------------------------------------------------
# 8. No duplicate IDs when creating tasks concurrently
# ---------------------------------------------------------------------------


def test_stress_no_duplicate_task_ids() -> None:
    """Creating render jobs and audio analyses from many threads
    simultaneously must never produce duplicate IDs."""
    state = get_runtime_state()
    all_ids: list[str] = []
    lock = threading.Lock()

    def create_render(i: int) -> None:
        record = state.create_render_job(
            provider="dup-check",
            tool=f"dup_render_{i}",
            operation=f"op_{i}",
            payload={"i": i},
            # Use uuid-based IDs (no explicit job_id) to stress the uuid path.
            result={"task_status": "queued"},
        )
        with lock:
            all_ids.append(record.id)

    def create_analysis(i: int) -> None:
        record = state.create_audio_analysis(
            provider="dup-check",
            tool=f"dup_analysis_{i}",
            operation=f"op_{i}",
            payload={"i": i},
            result={"task_status": "running"},
        )
        with lock:
            all_ids.append(record.id)

    with ThreadPoolExecutor(max_workers=STRESS_THREADS) as pool:
        futures = []
        for i in range(STRESS_THREADS):
            futures.append(pool.submit(create_render, i))
            futures.append(pool.submit(create_analysis, i))
        for f in as_completed(futures):
            f.result()

    total = STRESS_THREADS * 2
    assert len(all_ids) == total
    assert len(set(all_ids)) == total, (
        f"Duplicate task IDs detected: {len(all_ids)} total, {len(set(all_ids))} unique"
    )


# ---------------------------------------------------------------------------
# 9. Concurrent cancel + create on render jobs — no crashes
# ---------------------------------------------------------------------------


def test_stress_concurrent_cancel_and_create_render_jobs() -> None:
    """Concurrently creating and cancelling render jobs must not crash."""
    state = get_runtime_state()

    # Pre-seed jobs to cancel.
    seed_ids: list[str] = []
    for i in range(MIXED_THREADS):
        record = state.create_render_job(
            provider="cancel-stress",
            tool=f"cancel_tool_{i}",
            operation=f"cancel_op_{i}",
            payload={"i": i},
            result={"job_id": f"cancel-seed-{i}", "task_status": "queued"},
        )
        seed_ids.append(record.id)

    def cancel_job(job_id: str) -> None:
        state.cancel_render_job(job_id)

    def create_job(i: int) -> None:
        state.create_render_job(
            provider="cancel-stress",
            tool=f"new_tool_{i}",
            operation=f"new_op_{i}",
            payload={"i": i},
            result={"job_id": f"cancel-new-{i}", "task_status": "queued"},
        )

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        futures = []
        for sid in seed_ids:
            futures.append(pool.submit(cancel_job, sid))
        for i in range(MIXED_THREADS):
            futures.append(pool.submit(create_job, i))
        for f in as_completed(futures):
            f.result()

    # All seed jobs should be canceled.
    for sid in seed_ids:
        record = state.get_render_job(sid)
        assert record is not None
        assert record.state == "canceled"


# ---------------------------------------------------------------------------
# 10. Arrangement snapshot/replace under contention — no crashes
# ---------------------------------------------------------------------------


def test_stress_arrangement_snapshot_replace() -> None:
    """Concurrent snapshot_arrangement and replace_arrangement must not
    crash or produce partial arrangements."""
    from fl_mcp.schemas.runtime_surface import (
        ProjectArrangementModel,
        ProjectArrangementTrackModel,
    )

    state = get_runtime_state()
    errors: list[str] = []

    def do_replace(i: int) -> None:
        arr = ProjectArrangementModel(
            selected_arrangement=f"arr-{i}",
            tracks=[ProjectArrangementTrackModel(track_index=i, name=f"track-{i}")],
        )
        state.replace_arrangement(arr)

    def do_snapshot(_i: int) -> None:
        arr = state.snapshot_arrangement()
        if not isinstance(arr, ProjectArrangementModel):
            errors.append(f"snapshot returned non-ProjectArrangementModel: {type(arr)}")

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        futures = []
        for i in range(MIXED_THREADS):
            futures.append(pool.submit(do_snapshot, i))
            futures.append(pool.submit(do_replace, i))
        for f in as_completed(futures):
            f.result()

    assert not errors, f"Arrangement snapshot/replace errors: {errors}"


# ---------------------------------------------------------------------------
# 11. Engine singleton with patched database_url — isolation
# ---------------------------------------------------------------------------


def test_stress_get_engine_singleton_in_memory() -> None:
    """get_engine() returns the same instance across 50 threads even when
    using an in-memory SQLite database (verifies the lock, not the DB)."""
    import fl_mcp.persistence.db as db_mod

    with db_mod._ENGINE_LOCK:
        db_mod._ENGINE = None

    try:
        with patch.object(db_mod.settings, "database_url", "sqlite:///:memory:"):
            with ThreadPoolExecutor(max_workers=STRESS_THREADS) as pool:
                futures = [pool.submit(db_mod.get_engine) for _ in range(STRESS_THREADS)]
                instances = [f.result() for f in as_completed(futures)]

        assert len(instances) == STRESS_THREADS
        first = instances[0]
        assert all(inst is first for inst in instances)
    finally:
        engine = db_mod._ENGINE
        with db_mod._ENGINE_LOCK:
            db_mod._ENGINE = None
        if engine is not None:
            engine.dispose()


# ---------------------------------------------------------------------------
# 12. Provider registry: concurrent register + manifests() reads
# ---------------------------------------------------------------------------


def test_stress_registry_register_while_reading_manifests() -> None:
    """Registering providers while reading manifests() concurrently must
    not raise or corrupt the registry."""
    registry = ProviderRegistry()
    errors: list[str] = []

    def register(i: int) -> None:
        provider = _make_dummy(f"rw-provider-{i}")
        registry.register(provider)

    def read_manifests(_i: int) -> None:
        try:
            manifests = registry.manifests()
            # Manifests must be a list — never None or a partial object.
            if not isinstance(manifests, list):
                errors.append(f"manifests() returned {type(manifests)}")
        except Exception as exc:
            errors.append(f"manifests() raised: {exc}")

    with ThreadPoolExecutor(max_workers=MEDIUM_THREADS) as pool:
        futures = []
        for i in range(MIXED_THREADS):
            futures.append(pool.submit(register, i))
            futures.append(pool.submit(read_manifests, i))
        for f in as_completed(futures):
            f.result()

    assert not errors, f"Registry read/write errors: {errors}"
    assert len(registry.manifests()) == MIXED_THREADS
