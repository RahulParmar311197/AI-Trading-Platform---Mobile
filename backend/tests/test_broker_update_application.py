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


def service(tmp_path, broker, lifecycle):
    return OrderExecutionService(Router(broker), lifecycle, ExecutionStateStore(str(tmp_path/'state.json')), IdempotencyStore(str(tmp_path/'idem.sqlite3')), StartupRecoveryCoordinator())


def test_broker_partial_update_can_be_reconciled_into_lifecycle(tmp_path):
    broker = PaperBrokerAdapter(); lifecycle = OrderLifecycle(); svc = service(tmp_path, broker, lifecycle)
    req = BrokerOrderRequest('update-1', 'NIFTY', 'BUY', 10)
    first = svc.submit(req)
    broker.fill_order(first.broker_order_id, 4, 100)

    recovered = svc._save_recovered(req, broker.get_order(first.broker_order_id), 'BROKER_UPDATE')
    assert recovered.status == OrderStatus.PARTIALLY_FILLED.value
    assert lifecycle.orders['update-1'].filled_quantity == 4
    assert lifecycle.positions['NIFTY'].quantity == 4


def test_broker_final_update_is_applied_exactly_once(tmp_path):
    broker = PaperBrokerAdapter(); lifecycle = OrderLifecycle(); svc = service(tmp_path, broker, lifecycle)
    req = BrokerOrderRequest('update-2', 'NIFTY', 'BUY', 5)
    first = svc.submit(req)
    broker.fill_order(first.broker_order_id, 5, 101)

    first_recovery = svc._save_recovered(req, broker.get_order(first.broker_order_id), 'BROKER_UPDATE')
    before = lifecycle.positions['NIFTY'].quantity
    second_recovery = svc._save_recovered(req, broker.get_order(first.broker_order_id), 'BROKER_UPDATE_REPLAY')
    after = lifecycle.positions['NIFTY'].quantity

    assert first_recovery.status == OrderStatus.FILLED.value
    assert second_recovery.status == OrderStatus.FILLED.value
    assert before == 5
    assert after == before
