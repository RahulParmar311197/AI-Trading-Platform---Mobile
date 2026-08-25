import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.order_lifecycle import OrderLifecycle
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore


def test_router_uses_request_broker_route(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    primary = PaperBrokerAdapter()
    secondary = PaperBrokerAdapter()
    router = BrokerRouter([BrokerRoute("primary", primary), BrokerRoute("secondary", secondary)], "primary", safety_store=store)
    request = BrokerOrderRequest("CID-1", "NIFTY", "BUY", 1, broker_account_id=2, broker_route="secondary")
    result = router.submit(request)
    assert result.order_id == "PAPER-1"
    assert secondary.get_orders()[0]["client_order_id"] == "CID-1"
    assert primary.get_orders() == []


def test_lifecycle_persists_account_binding():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("CID-1", "NIFTY", "BUY", 1, owner_user_id=7, broker_account_id=2, broker_route="secondary")
    assert order.broker_account_id == 2
    assert order.broker_route == "secondary"


def test_runtime_risk_snapshot_requires_bound_route():
    class Router:
        safety_store = None
    provider = RuntimeRiskSnapshotProvider(Router(), OrderLifecycle())
    request = BrokerOrderRequest("CID-1", "NIFTY", "BUY", 1, price=100, stop=99, broker_account_id=2)
    with pytest.raises(RuntimeError, match="broker account route is required"):
        provider(request)
