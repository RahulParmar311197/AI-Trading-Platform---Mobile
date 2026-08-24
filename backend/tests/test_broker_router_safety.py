import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self):
        self.submit_called = False
        self.cancelled = []

    def submit_order(self, request):
        self.submit_called = True
        return BrokerOrderUpdate(order_id="B1", status="NEW", client_order_id=request.client_order_id)

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        return BrokerOrderUpdate(order_id=order_id, status="CANCELLED")

    def get_order(self, order_id): return {}
    def get_positions(self): return []
    def get_account(self): return {}


def req():
    return BrokerOrderRequest(client_order_id="t1", symbol="NIFTY", side="BUY", quantity=1)


def test_persisted_halt_cannot_be_overridden(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json")); store.halt("BROKER_STATE_DRIFT")
    broker = Broker(); router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)
    with pytest.raises(RuntimeError, match="TRADING_HALTED"): router.submit(req())
    assert broker.submit_called is False


def test_persisted_ready_allows_submission(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json")); store.clear()
    broker = Broker(); router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)
    router.submit(req()); assert broker.submit_called is True


def test_missing_safety_store_fails_closed():
    broker = Broker(); router = BrokerRouter([BrokerRoute("test", broker)], "test")
    with pytest.raises(RuntimeError, match="TRADING_HALTED"): router.submit(req())
    assert broker.submit_called is False


def test_ready_state_allows_cancellation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json")); store.clear()
    broker = Broker(); router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)
    result = router.cancel("B1")
    assert result.status == "CANCELLED"
    assert broker.cancelled == ["B1"]


def test_halted_state_blocks_cancellation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json")); store.halt("BROKER_STATE_DRIFT")
    broker = Broker(); router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=store)
    with pytest.raises(RuntimeError, match="TRADING_HALTED"): router.cancel("B1")
    assert broker.cancelled == []
