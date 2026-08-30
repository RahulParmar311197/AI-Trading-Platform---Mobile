from types import SimpleNamespace

from app.api.orders import _matches_order_broker_identity


def _order(account_id=1, route="upstox:account:1", generation="account:1:g1"):
    return SimpleNamespace(
        broker_account_id=account_id,
        broker_route=route,
        broker_route_generation=generation,
    )


def _result(account_id="1", route="upstox:account:1", generation="account:1:g1"):
    return SimpleNamespace(
        broker_account_id=account_id,
        broker_route=route,
        broker_route_generation=generation,
    )


def test_cancellation_accepts_equivalent_numeric_account_identity():
    assert _matches_order_broker_identity(_order(1), _result("1"))


def test_cancellation_rejects_distinct_opaque_account_identity():
    assert not _matches_order_broker_identity(_order("001"), _result("1"))


def test_cancellation_rejects_route_mismatch():
    assert not _matches_order_broker_identity(_order(), _result(route="upstox:account:2"))


def test_cancellation_rejects_route_generation_mismatch():
    assert not _matches_order_broker_identity(_order(), _result(generation="account:1:g2"))


def test_cancellation_allows_legacy_response_without_optional_identity_fields():
    result = _result()
    result.broker_account_id = None
    result.broker_route = None
    result.broker_route_generation = None
    assert _matches_order_broker_identity(_order(), result)
