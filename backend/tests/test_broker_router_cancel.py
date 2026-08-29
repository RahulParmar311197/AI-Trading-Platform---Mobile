import pytest

from app.broker_adapter import BrokerAdapter, BrokerOrderUpdate, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter


class MismatchedCancelAdapter(PaperBrokerAdapter):
    def cancel_order(self, broker_order_id: str):
        return BrokerOrderUpdate(order_id="OTHER", status="CANCELLED")


class UnconfirmedCancelAdapter(PaperBrokerAdapter):
    def cancel_order(self, broker_order_id: str):
        return BrokerOrderUpdate(order_id=broker_order_id, status="NEW", client_order_id="c", symbol="ABC", side="BUY", quantity=1)


def make_router(adapter: BrokerAdapter, account_id: int = 7) -> BrokerRouter:
    route = BrokerRoute(name="paper:account:7", adapter=adapter, broker_account_id=account_id, generation="gen-1")
    return BrokerRouter([route], route.name)


def test_cancel_rejects_broker_identity_mismatch():
    router = make_router(MismatchedCancelAdapter())
    with pytest.raises(RuntimeError, match="order identity mismatch"):
        router.cancel("PAPER-00000001", route="paper:account:7", broker_account_id=7)


def test_cancel_rejects_unconfirmed_broker_status():
    router = make_router(UnconfirmedCancelAdapter())
    with pytest.raises(RuntimeError, match="was not confirmed"):
        router.cancel("PAPER-00000001", route="paper:account:7", broker_account_id=7)


def test_cancel_accepts_confirmed_terminal_status():
    adapter = PaperBrokerAdapter()
    request = type("Request", (), {
        "client_order_id": "cancel-test",
        "symbol": "ABC",
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
        "price": 100,
        "stop": None,
        "security_id": "",
        "broker_account_id": 7,
    })()
    submitted = adapter.submit_order(request)
    router = make_router(adapter)
    result = router.cancel(submitted["order_id"], route="paper:account:7", broker_account_id=7)
    assert result.order_id == submitted["order_id"]
    assert result.status == "FILLED"


def test_cancel_rejects_cross_account_route_binding():
    router = make_router(PaperBrokerAdapter(), account_id=7)
    with pytest.raises(RuntimeError, match="does not match broker route"):
        router.cancel("PAPER-00000001", route="paper:account:7", broker_account_id=8)
