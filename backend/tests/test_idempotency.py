from app.idempotency import (
    InMemoryIdempotencyStore,
    claim_order,
    order_fingerprint,
    order_idempotency_key,
)


def _order():
    return {"symbol": "NIFTY", "side": "BUY", "quantity": 50, "price": 25000}


def test_same_request_is_claimed_only_once():
    store = InMemoryIdempotencyStore()
    first = claim_order(
        store,
        account_id="acct-1",
        broker="Dhan",
        request_id="req-1",
        order=_order(),
    )
    second = claim_order(
        store,
        account_id="acct-1",
        broker="Dhan",
        request_id="req-1",
        order=_order(),
    )
    assert first.claimed is True
    assert second.claimed is False
    assert second.conflict is False
    assert first.fingerprint == second.fingerprint


def test_different_requests_do_not_collide():
    store = InMemoryIdempotencyStore()
    first = claim_order(store, account_id="acct-1", broker="dhan", request_id="req-1", order=_order())
    second = claim_order(store, account_id="acct-1", broker="dhan", request_id="req-2", order=_order())
    assert first.claimed is True
    assert second.claimed is True
    assert first.key != second.key


def test_reused_request_id_with_different_order_is_a_conflict():
    store = InMemoryIdempotencyStore()
    first = claim_order(
        store,
        account_id="acct-1",
        broker="dhan",
        request_id="req-1",
        order=_order(),
    )
    changed = {**_order(), "quantity": 100}
    second = claim_order(
        store,
        account_id="acct-1",
        broker="dhan",
        request_id="req-1",
        order=changed,
    )
    assert first.claimed is True
    assert second.claimed is False
    assert second.conflict is True
    assert second.fingerprint != first.fingerprint


def test_canonical_fingerprint_is_order_independent():
    assert order_fingerprint({"b": 2, "a": 1}) == order_fingerprint({"a": 1, "b": 2})


def test_key_requires_all_identity_parts():
    assert order_idempotency_key(account_id="a", broker="Dhan", request_id="r") == "trade:idempotency:a:dhan:r"
