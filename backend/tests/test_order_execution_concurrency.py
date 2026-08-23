from concurrent.futures import ThreadPoolExecutor

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore


class SlowBroker:
    def __init__(self):
        self.calls = 0
    def submit_order(self, request):
        self.calls += 1
        return BrokerOrderUpdate(order_id="B-1", status="FILLED", price=100)
    def cancel_order(self, order_id): raise NotImplementedError
    def get_order(self, order_id): raise NotImplementedError
    def get_positions(self): return []
    def get_account(self): return {}
    def get_orders(self): return []


def test_concurrent_same_client_order_submits_once(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = SlowBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    service = OrderExecutionService(router, OrderLifecycle(), ExecutionStateStore(str(tmp_path / "execution.json")))
    request = BrokerOrderRequest(client_order_id="same", symbol="NIFTY", side="BUY", quantity=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.submit, [request, request]))

    assert broker.calls == 1
    assert sorted(r.status for r in results) == ["FILLED", "FILLED"]
