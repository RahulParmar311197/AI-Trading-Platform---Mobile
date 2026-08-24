from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.startup_recovery import StartupRecoveryCoordinator

class Router:
    def __init__(self, broker): self.broker = broker
    def submit(self, request): return self.broker.submit_order(request)
    def find_order_by_client_id(self, client_id): return self.broker.find_order_by_client_id(client_id)


def test_execution_service_handles_new_then_partial_then_full_fill(tmp_path):
    broker = PaperBrokerAdapter(); lifecycle = OrderLifecycle()
    service = OrderExecutionService(Router(broker), lifecycle, ExecutionStateStore(str(tmp_path/'state.json')), IdempotencyStore(str(tmp_path/'idem.sqlite3')), StartupRecoveryCoordinator())
    request = BrokerOrderRequest('e2e-paper-1', 'NIFTY', 'BUY', 10)
    first = service.submit(request)
    assert first.status == OrderStatus.SUBMITTED.value
    broker_id = first.broker_order_id
    partial = broker.fill_order(broker_id, 4, 100)
    lifecycle.transition(request.client_order_id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    assert partial.status == 'PARTIALLY_FILLED'
    final = broker.fill_order(broker_id, 6, 101)
    lifecycle.transition(request.client_order_id, OrderStatus.FILLED, filled_quantity=10, fill_price=101)
    assert final.status == 'FILLED'
    assert lifecycle.positions['NIFTY'].quantity == 10


def test_execution_service_recovers_existing_paper_order_without_duplicate(tmp_path):
    broker = PaperBrokerAdapter(); request = BrokerOrderRequest('e2e-paper-2', 'NIFTY', 'BUY', 5)
    first_order = broker.submit_order(request)
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(Router(broker), lifecycle, ExecutionStateStore(str(tmp_path/'state.json')), IdempotencyStore(str(tmp_path/'idem.sqlite3')), StartupRecoveryCoordinator())
    result = service.submit(request)
    assert result.broker_order_id == first_order.order_id
    assert broker.get_orders().__len__() == 1
