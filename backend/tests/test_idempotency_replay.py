from app.idempotency_store import IdempotencyStore


def test_duplicate_client_order_id_has_single_claim(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    assert store.claim("client-123") is True
    assert store.claim("client-123") is False
    assert store.get_state("client-123") == "CLAIMED"


def test_completed_claim_survives_store_restart(tmp_path):
    path = str(tmp_path / "idempotency.sqlite3")
    first = IdempotencyStore(path)
    assert first.claim("client-retry") is True
    first.mark_completed("client-retry")

    second = IdempotencyStore(path)
    assert second.get_state("client-retry") == "COMPLETED"
    assert second.claim("client-retry") is False
