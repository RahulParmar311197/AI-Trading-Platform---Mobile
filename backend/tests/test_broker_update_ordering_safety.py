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

def make_service(tmp_path):
    broker = PaperBrokerAdapter(); lifecycle = OrderLifecycle()
    svc = OrderExecutionService(Router(broker), lifecycle, ExecutionStateStore(str(tmp_path/'state.json')), IdempotencyStore(str(tmp_path/'idem.sqlite3')), StartupRecoveryCoordinator())
    return broker, lifecycle, svc

def test_replayed_partial_fill_does_not_inflate_position(tmp_path):
    broker, lifecycle, svc = make_service(tmp_path)
    req = BrokerOrderRequest('ordering-1', 'NIFTY', 'BUY', 10)
    first = svc.submit(req)
    broker.fill_order(first.broker_order_id, 4, 100)
    update = broker.get_order(first.broker_order_id)
    svc._save_recovered(req, update, 'UPDATE')
    svc._save_recovered(req, update, 'UPDATE_REPLAY')
    assert lifecycle.positions['NIFTY'].quantity == 4

def test_stale_partial_after_fill_does_not_move_terminal_order_backwards(tmp_path):
    broker, lifecycle, svc = make_service(tmp_path)
    req = BrokerOrderRequest('ordering-2', 'NIFTY', 'BUY', 10)
    first = svc.submit(req)
    broker.fill_order(first.broker_order_id, 10, 101)
    filled = broker.get_order(first.broker_order_id)
    svc._save_recovered(req, filled, 'FILLED')
    # Simulate a stale broker snapshot received after the terminal state.
    stale = dict(filled); stale['status'] = 'PARTIALLY_FILLED'; stale['filled_quantity'] = 4
    recovered = svc._save_recovered(req, stale, 'STALE')
    assert recovered.status == OrderStatus.FILLED.value
    assert lifecycle.positions['NIFTY'].quantity == 10

def test_malformed_fill_quantity_is_rejected_fail_closed(tmp_path):
    broker, lifecycle, svc = make_service(tmp_path)
    req = BrokerOrderRequest('ordering-3', 'NIFTY', 'BUY', 10)
    first = svc.submit(req)
    malformed = broker.get_order(first.broker_order_id)
    malformed['filled_quantity'] = 99
    try:
        svc._save_recovered(req, malformed, 'MALFORMED')
    except (ValueError, RuntimeError, KeyError):
        pass
    assert lifecycle.positions.get('NIFTY', type('P', (), {'quantity': 0})()).quantity == 0
