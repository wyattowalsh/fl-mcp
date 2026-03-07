from fl_mcp.transaction.envelope import (
    rollback_classification_presence,
    validate_envelope,
)


def test_transaction_envelope_validation_and_rollback_classifications() -> None:
    envelope = {"transaction_id": "tx-1", "operations": [{"op": "noop"}]}

    assert validate_envelope(envelope) is True
    assert validate_envelope({"transaction_id": "tx-2"}) is False

    classifications = rollback_classification_presence()
    assert {"validation_error", "provider_error", "timeout"}.issubset(classifications)
