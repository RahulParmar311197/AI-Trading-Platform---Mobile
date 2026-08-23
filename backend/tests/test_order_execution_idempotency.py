from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self):
        self.calls = 0
    def submit_order(self, request):
        self.calls += 1
        return BrokerOrderUpdate(order_id=f"B-{self.calls}", status="FILLED", price=100)
    def cancel_order(self, order_id): raise NotImplementedError
    def get_order(self, order_id): raise NotImplementedError
    def get_positions(self): return []
    def get_account(self): return {}


def test_duplicate_client_order_is_idempotent(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")))
    request = BrokerOrderRequest(client_order_id="same-id", symbol="NIFTY", side="BUY", quantity=1)

    first = service.submit(request)
    second = service.submit(request)

    assert first.status == "FILLED"
    assert second.message == "IDEMPOTENT_REPLAY"
    assert second.broker_order_id == first.broker_order_id
    assert broker.calls == 1
