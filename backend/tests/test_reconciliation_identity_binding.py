from datetime import datetime, timezone

from app.order_identity_registry import OrderIdentityRegistry
from app.reconciliation_identity_binding import ReconciliationIdentityBinder
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate


def test_binds_under_actual_broker_name(tmp_path):
    registry = OrderIdentityRegistry(str(tmp_path / "identity.db"))
    now = datetime.now(timezone.utc)
    binder = ReconciliationIdentityBinder(registry)
    result = binder.bind("upstox", BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now), [InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)])
    assert result.bound is True
    assert registry.by_broker("upstox", "b1").client_order_id == "client-1"
    assert registry.by_broker("reconciliation", "b1") is None
    registry.close()


def test_conflicting_existing_binding_is_rejected(tmp_path):
    registry = OrderIdentityRegistry(str(tmp_path / "identity.db"))
    now = datetime.now(timezone.utc)
    binder = ReconciliationIdentityBinder(registry)
    binder.bind("upstox", BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now), [InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)])
    result = binder.bind("upstox", BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now), [InternalOrderCandidate("client-2", "NIFTY", "BUY", 5, now)])
    assert result.bound is False
    assert result.reason == "BROKER_ORDER_ALREADY_BOUND"
    registry.close()
