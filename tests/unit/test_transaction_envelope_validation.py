from fl_mcp.transactions.envelope import (
    rollback_classification_presence,
    validate_envelope,
)


def test_transaction_envelope_validation_and_rollback_classifications() -> None:
    envelope = {
        "request_id": "tx-1",
        "mode": "preview",
        "changes": [{"domain": "mixer", "operation": "noop", "rollback_class": "best_effort"}],
    }

    assert validate_envelope(envelope) is True
    assert validate_envelope({"request_id": "tx-2"}) is False

    classifications = rollback_classification_presence()
    assert {"validation_error", "provider_error", "timeout"}.issubset(classifications)
