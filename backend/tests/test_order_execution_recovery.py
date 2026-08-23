from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self):
        self.calls = 0
        self.orders = [{"order_id": "B-99", "client_order_id": "crashed-1", "status": "FILLED", "price": 101}]
    def submit_order(self, request):
        self.calls += 1
        return BrokerOrderUpdate(order_id="NEW", status="FILLED", price=100)
    def cancel_order(self, order_id): raise NotImplementedError
    def get_order(self, order_id): raise NotImplementedError
    def get_orders(self): return list(self.orders)
    def get_positions(self): return []
    def get_account(self): return {}


def test_existing_broker_order_is_recovered_without_resubmit(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")))

    result = service.submit(BrokerOrderRequest(client_order_id="crashed-1", symbol="NIFTY", side="BUY", quantity=1))

    assert result.message == "BROKER_ORDER_RECOVERED"
    assert result.broker_order_id == "B-99"
    assert result.status == OrderStatus.FILLED.value
    assert broker.calls == 0
