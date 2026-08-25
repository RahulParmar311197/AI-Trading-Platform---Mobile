import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self):
        self.submit_called = False

    def submit_order(self, request):
        self.submit_called = True
        return BrokerOrderUpdate(order_id="B1", status="NEW", client_order_id=request.client_order_id)

    def cancel_order(self, order_id):
        return BrokerOrderUpdate(order_id=order_id, status="CANCELLED")

    def get_order(self, order_id):
        return {}

    def get_positions(self):
        return []

    def get_account(self):
        return {"status": "READY"}

    def get_snapshot(self):
        return BrokerSnapshot(orders=[], positions=[])


def request(account_id: int) -> BrokerOrderRequest:
    return BrokerOrderRequest(
        client_order_id="acct-safe-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        broker_account_id=account_id,
        broker_route="acct-route",
        price=100,
        stop=99,
    )


def test_router_stamps_snapshot_with_bound_route_account(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    broker = Broker()
    router = BrokerRouter(
        [BrokerRoute("acct-route", broker, broker_account_id=42)],
        "acct-route",
        safety_store=store,
    )

    snapshot = router.get_snapshot("acct-route")

    assert snapshot.broker_route == "acct-route"
    assert snapshot.broker_account_id == 42


def test_router_rejects_order_for_different_account_before_submit(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    broker = Broker()
    router = BrokerRouter(
        [BrokerRoute("acct-route", broker, broker_account_id=42)],
        "acct-route",
        safety_store=store,
    )

    with pytest.raises(RuntimeError, match="does not match broker route"):
        router.submit(request(43))

    assert broker.submit_called is False


def test_router_rejects_account_bound_order_when_route_is_unbound(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    broker = Broker()
    router = BrokerRouter(
        [BrokerRoute("acct-route", broker)],
        "acct-route",
        safety_store=store,
    )

    with pytest.raises(RuntimeError, match="not bound to a broker account"):
        router.submit(request(42))

    assert broker.submit_called is False


def test_runtime_risk_rejects_snapshot_account_binding_mismatch(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    broker = Broker()
    router = BrokerRouter(
        [BrokerRoute("acct-route", broker, broker_account_id=42)],
        "acct-route",
        safety_store=store,
    )
    provider = RuntimeRiskSnapshotProvider(router, lifecycle=object())

    with pytest.raises(RuntimeError, match="account binding mismatch"):
        provider(request(43))
