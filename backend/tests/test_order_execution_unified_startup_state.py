from app.broker_adapter import BrokerOrderRequest
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


class Router:
    def __init__(self): self.submit_calls = 0
    def submit(self, request):
        self.submit_calls += 1
        raise AssertionError("broker must not be called while startup is locked")
    def find_order_by_client_id(self, client_order_id): return None


def test_unified_startup_state_blocks_execution(tmp_path):
    state = StartupExecutionStateMachine()
    service = OrderExecutionService(
        Router(), OrderLifecycle(), ExecutionStateStore(str(tmp_path / "execution.json")),
        startup_state=state,
    )
    request = BrokerOrderRequest(client_order_id="startup-state-1", symbol="NIFTY", side="BUY", quantity=1)
    result = service.submit(request)
    assert result.status == "REJECTED"
    assert "STARTUP_EXECUTION_LOCKED" in (result.message or "")


def test_ready_unified_startup_state_allows_service_to_continue_to_idempotency(tmp_path):
    state = StartupExecutionStateMachine()
    for value in (
        StartupExecutionState.RECOVERING,
        StartupExecutionState.BROKER_RECONCILED,
        StartupExecutionState.PORTFOLIO_RECONCILED,
        StartupExecutionState.RISK_READY,
        StartupExecutionState.READY,
    ):
        state.transition(value)
    router = Router()
    service = OrderExecutionService(router, OrderLifecycle(), ExecutionStateStore(str(tmp_path / "execution.json")), startup_state=state)
    request = BrokerOrderRequest(client_order_id="startup-state-2", symbol="NIFTY", side="BUY", quantity=1)
    result = service.submit(request)
    assert result.status == "SUBMITTED"
    assert result.message == "EXECUTION_PENDING_RECONCILIATION"
    assert router.submit_calls == 0
