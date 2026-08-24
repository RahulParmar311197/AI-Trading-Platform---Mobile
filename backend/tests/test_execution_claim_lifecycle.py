from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


class Broker:
    def __init__(self, status="FILLED"):
        self.status = status

    def submit_order(self, request):
        return BrokerOrderUpdate(order_id="B-1", status=self.status, price=100.0)

    def cancel_order(self, order_id):
        raise NotImplementedError

    def get_order(self, order_id):
        raise NotImplementedError

    def get_orders(self):
        return []

    def get_positions(self):
        return []

    def get_account(self):
        return {}


def ready_state():
    state = StartupExecutionStateMachine()
    state.transition(StartupExecutionState.RECOVERING)
    state.transition(StartupExecutionState.BROKER_RECONCILED)
    state.transition(StartupExecutionState.PORTFOLIO_RECONCILED)
    state.transition(StartupExecutionState.RISK_READY)
    state.transition(StartupExecutionState.READY)
    return state


def make_service(tmp_path, status):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    router = BrokerRouter([BrokerRoute("test", Broker(status))], "test", safety_store=safety)
    return OrderExecutionService(
        router,
        OrderLifecycle(),
        ExecutionStateStore(str(tmp_path / "execution.json")),
        idempotency_store=IdempotencyStore(str(tmp_path / "idempotency.sqlite3")),
        safety_state_store=safety,
        startup_state=ready_state(),
    )


def request():
    return BrokerOrderRequest(client_order_id="L-CLAIM", symbol="NIFTY", side="BUY", quantity=1, price=100)


def test_terminal_submission_completes_persistent_claim(tmp_path):
    svc = make_service(tmp_path, "FILLED")
    result = svc.submit(request())
    assert result.status == "FILLED"
    assert svc.idempotency_store.get_claim("L-CLAIM")["state"] == "COMPLETED"


def test_rejected_submission_completes_persistent_claim(tmp_path):
    svc = make_service(tmp_path, "REJECTED")
    result = svc.submit(request())
    assert result.status == "REJECTED"
    assert svc.idempotency_store.get_claim("L-CLAIM")["state"] == "COMPLETED"


def test_partial_submission_keeps_claim_for_reconciliation(tmp_path):
    svc = make_service(tmp_path, "PARTIALLY_FILLED")
    result = svc.submit(request())
    assert result.status == "PARTIALLY_FILLED"
    assert svc.idempotency_store.get_claim("L-CLAIM")["state"] == "CLAIMED"
