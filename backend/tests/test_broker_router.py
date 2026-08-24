import pytest

from app.broker_adapter import PaperBrokerAdapter, BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


def test_default_route_submits():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=None)
    # No safety store means the router must fail closed for live execution.
    with pytest.raises(Exception):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def test_disabled_route_rejected():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),False)],'paper')
    with pytest.raises(ValueError):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def _ready_router(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=store)
    return router, store


def test_cancel_blocked_when_halted(tmp_path):
    router, store = _ready_router(tmp_path)
    store.halt('test halt')
    with pytest.raises(Exception):
        router.cancel('missing-order')


def test_cancel_requires_order_id(tmp_path):
    router, _ = _ready_router(tmp_path)
    with pytest.raises(ValueError, match='order_id is required'):
        router.cancel('')
