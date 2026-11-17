from fl_mcp.schemas import DomainChange, TransactionEnvelope
from fl_mcp.transactions.planner import plan_changes


def test_planner_smoke_speed() -> None:
    env = TransactionEnvelope(
        request_id="bench",
        mode="preview",
        changes=[DomainChange(domain="patterns", operation="noop", rollback_class="best_effort")],
    )
    plan_changes(env)
