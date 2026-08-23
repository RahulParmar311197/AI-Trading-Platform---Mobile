import pytest

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self):
        self.called = False

    def submit_order(self, request):
        self.called = True
        return {"status": "FILLED"}

    def cancel_order(self, order_id):
        return {"status": "CANCELLED"}

    def get_order(self, order_id):
        return {}

    def get_positions(self):
        return []

    def get_account(self):
        return {}


def req():
    return BrokerOrderRequest(client_order_id="t1", symbol="NIFTY", side="BUY", quantity=1)


def test_persisted_halt_cannot_be_overridden(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("BROKER_STATE_DRIFT")
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)

    with pytest.raises(RuntimeError, match="TRADING_HALTED"):
        router.submit(req())
    assert broker.called is False


def test_persisted_ready_allows_submission(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)
    router.submit(req())
    assert broker.called is True


def test_missing_safety_store_fails_closed():
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test")
    with pytest.raises(RuntimeError, match="TRADING_HALTED"):
        router.submit(req())
    assert broker.called is False
