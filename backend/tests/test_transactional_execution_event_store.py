from app.transactional_execution_event_store import TransactionalExecutionEventStore


def test_claim_is_idempotent(tmp_path):
    path = str(tmp_path / "claims.db")
    store = TransactionalExecutionEventStore(path)
    assert store.claim("evt-1") is True
    assert store.claim("evt-1") is False
    store.close()

    reopened = TransactionalExecutionEventStore(path)
    assert reopened.claim("evt-1") is False
    assert reopened.claim("evt-2") is True
    reopened.close()
