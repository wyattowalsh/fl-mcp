from fl_mcp.schemas import DomainChange, TransactionEnvelope


def test_transaction_envelope_requires_rollback_class() -> None:
    env = TransactionEnvelope(
        request_id="abc",
        mode="preview",
        changes=[DomainChange(domain="mixer", operation="set_volume", rollback_class="checkpointed")],
    )
    assert env.changes[0].rollback_class == "checkpointed"
