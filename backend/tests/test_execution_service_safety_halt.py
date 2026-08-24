from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore
from app.startup_recovery import StartupRecoveryCoordinator

class Router:
    def __init__(self, broker): self.broker = broker
    def submit(self, request): return self.broker.submit_order(request)
    def find_order_by_client_id(self, client_id): return self.broker.find_order_by_client_id(client_id)

def test_service_blocks_before_broker_submission_when_halted(tmp_path):
    broker = PaperBrokerAdapter()
    safety = SafetyStateStore(str(tmp_path / 'safety.json'))
    safety.halt('PORTFOLIO_MISMATCH: NIFTY')
    service = OrderExecutionService(Router(broker), OrderLifecycle(), ExecutionStateStore(str(tmp_path / 'state.json')), IdempotencyStore(str(tmp_path / 'idem.sqlite3')), StartupRecoveryCoordinator(), safety_state_store=safety)
    result = service.submit(BrokerOrderRequest('halt-1', 'NIFTY', 'BUY', 1))
    assert result.status == 'REJECTED'
    assert 'TRADING_HALTED' in result.message
    assert broker.get_orders() == []


def test_service_allows_submission_after_halt_cleared(tmp_path):
    broker = PaperBrokerAdapter()
    safety = SafetyStateStore(str(tmp_path / 'safety.json'))
    safety.halt('PORTFOLIO_MISMATCH: NIFTY')
    safety.clear()
    service = OrderExecutionService(Router(broker), OrderLifecycle(), ExecutionStateStore(str(tmp_path / 'state.json')), IdempotencyStore(str(tmp_path / 'idem.sqlite3')), StartupRecoveryCoordinator(), safety_state_store=safety)
    result = service.submit(BrokerOrderRequest('halt-2', 'NIFTY', 'BUY', 1))
    assert result.broker_order_id is not None
    assert len(broker.get_orders()) == 1
