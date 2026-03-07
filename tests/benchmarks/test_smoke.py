import time

from fl_mcp.transactions.planner import plan_changes
from fl_mcp.schemas import DomainChange, TransactionEnvelope


def test_planner_smoke_speed() -> None:
    env = TransactionEnvelope(
        request_id="bench",
        mode="preview",
        changes=[DomainChange(domain="patterns", operation="noop", rollback_class="best_effort")],
    )
    start = time.perf_counter()
    plan_changes(env)
    assert time.perf_counter() - start < 1.0
