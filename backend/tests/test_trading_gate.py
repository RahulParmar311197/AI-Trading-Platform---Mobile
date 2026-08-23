import pytest

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter
from app.trading_gate import TradingGate


class RecordingBroker:
    def __init__(self):
        self.submitted = False

    def submit_order(self, order):
        self.submitted = True
        return {"status": "FILLED"}

    def cancel_order(self, broker_order_id):
        return {"status": "CANCELLED"}

    def get_order(self, broker_order_id):
        return {}

    def get_positions(self):
        return []

    def get_account(self):
        return {}


def request():
    return BrokerOrderRequest(client_order_id="t1", symbol="NIFTY", side="BUY", quantity=1)


def test_halted_trading_cannot_submit():
    broker = RecordingBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", TradingGate())
    with pytest.raises(RuntimeError, match="TRADING_HALTED"):
        router.submit(request(), trading_halted=True)
    assert broker.submitted is False


def test_ready_trading_can_submit():
    broker = RecordingBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", TradingGate())
    router.submit(request(), trading_halted=False)
    assert broker.submitted is True
