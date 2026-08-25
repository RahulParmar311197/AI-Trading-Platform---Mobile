from app.idempotency_store import IdempotencyStore


def test_claim_is_atomic_and_persistent(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    first = IdempotencyStore(str(path))
    second = IdempotencyStore(str(path))

    assert first.claim("order-1", "exec-1") is True
    assert second.claim("order-1", "exec-2") is False

    claim = second.get_claim("order-1")
    assert claim["state"] == "CLAIMED"
    assert claim["execution_id"] == "exec-1"


def test_completed_claim_cannot_be_released(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    assert store.claim("order-2", "exec-1") is True
    store.mark_completed("order-2")
    store.release("order-2")
    assert store.get_state("order-2") == "COMPLETED"


def test_unsubmitted_claim_can_be_explicitly_released(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    assert store.claim("order-3", "exec-1") is True
    store.release("order-3")
    assert store.get_state("order-3") is None
    assert store.claim("order-3", "exec-2") is True
