from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


class Router:
    def __init__(self, broker):
        self.broker = broker

    def submit(self, request, route=None):
        return self.broker.submit_order(request)

    def find_order_by_client_id(self, client_id, route=None):
        return self.broker.find_order_by_client_id(client_id)


def make(tmp_path):
    broker = PaperBrokerAdapter()
    lifecycle = OrderLifecycle()
    startup_state = StartupExecutionStateMachine()
    for state in (
        StartupExecutionState.RECOVERING,
        StartupExecutionState.BROKER_RECONCILED,
        StartupExecutionState.PORTFOLIO_RECONCILED,
        StartupExecutionState.RISK_READY,
        StartupExecutionState.READY,
    ):
        startup_state.transition(state)
    svc = OrderExecutionService(
        Router(broker),
        lifecycle,
        ExecutionStateStore(str(tmp_path / "state.json")),
        IdempotencyStore(str(tmp_path / "idem.sqlite3")),
        startup_state=startup_state,
    )
    return broker, lifecycle, svc


def recover(svc, request, record, reason):
    return svc._save_recovered(request, record, reason, f"test-{request.client_order_id}-{reason}")


def test_stale_partial_after_cancel_does_not_reopen_order(tmp_path):
    broker, lifecycle, svc = make(tmp_path)
    req = BrokerOrderRequest("terminal-cancel-1", "NIFTY", "BUY", 10)
    first = svc.submit(req)
    broker.cancel_order(first.broker_order_id)
    cancelled = broker.get_order(first.broker_order_id)
    recover(svc, req, cancelled, "CANCELLED")
    stale = dict(cancelled)
    stale["status"] = "PARTIALLY_FILLED"
    stale["filled_quantity"] = 3
    recovered = recover(svc, req, stale, "STALE_PARTIAL")
    assert recovered.status == OrderStatus.CANCELLED.value
    assert lifecycle.positions.get("NIFTY", type("P", (), {"quantity": 0})()).quantity == 0


def test_stale_open_after_rejection_does_not_reopen_order(tmp_path):
    broker, lifecycle, svc = make(tmp_path)
    req = BrokerOrderRequest("terminal-reject-1", "NIFTY", "BUY", 5)
    first = svc.submit(req)
    broker.reject_order(first.broker_order_id)
    rejected = broker.get_order(first.broker_order_id)
    recover(svc, req, rejected, "REJECTED")
    stale = dict(rejected)
    stale["status"] = "NEW"
    stale["filled_quantity"] = 0
    recovered = recover(svc, req, stale, "STALE_NEW")
    assert recovered.status == OrderStatus.REJECTED.value
    assert lifecycle.positions.get("NIFTY", type("P", (), {"quantity": 0})()).quantity == 0


def test_partial_fill_then_cancel_preserves_only_actual_fill(tmp_path):
    broker, lifecycle, svc = make(tmp_path)
    req = BrokerOrderRequest("terminal-cancel-2", "NIFTY", "BUY", 10)
    first = svc.submit(req)
    broker.fill_order(first.broker_order_id, 4, 100)
    recover(svc, req, broker.get_order(first.broker_order_id), "PARTIAL")
    broker.cancel_order(first.broker_order_id)
    cancelled = recover(svc, req, broker.get_order(first.broker_order_id), "CANCELLED")
    assert cancelled.status == OrderStatus.CANCELLED.value
    assert lifecycle.positions["NIFTY"].quantity == 4
