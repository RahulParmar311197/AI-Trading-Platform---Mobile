import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import RiskDecision, RiskSnapshot
from app.safety_state import SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine

class Broker:
    def __init__(self, status="FILLED"): self.status = status
    def submit_order(self, request): return BrokerOrderUpdate(order_id="B-1", status=self.status, client_order_id=request.client_order_id, symbol=request.symbol, side=request.side, quantity=request.quantity, filled_quantity=request.quantity if self.status == "FILLED" else 0, price=100.0, average_price=100.0)
    def cancel_order(self, order_id): raise NotImplementedError
    def get_order(self, order_id): raise NotImplementedError
    def get_orders(self): return []
    def get_positions(self): return []
    def get_account(self): return {"status": "READY"}

def req(): return BrokerOrderRequest(client_order_id="L-1", symbol="NIFTY", side="BUY", quantity=1, price=100, stop=90, broker_account_id=1, broker_route="test")

def ready_state():
    state = StartupExecutionStateMachine(); state.transition(StartupExecutionState.RECOVERING); state.transition(StartupExecutionState.BROKER_RECONCILED); state.transition(StartupExecutionState.PORTFOLIO_RECONCILED); state.transition(StartupExecutionState.RISK_READY); state.transition(StartupExecutionState.READY); return state

def service(tmp_path, status="FILLED", risk_gate=None, risk_provider=None, observability=None):
    safety = SafetyStateStore(str(tmp_path / "safety.json")); safety.clear(); router = BrokerRouter([BrokerRoute("test", Broker(status))], "test", safety_store=safety); lifecycle = OrderLifecycle()
    return OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")), risk_gate=risk_gate, risk_snapshot_provider=risk_provider, startup_state=ready_state(), observability=observability), lifecycle

def test_filled_order_updates_lifecycle_and_persists(tmp_path):
    svc, lifecycle = service(tmp_path); result = svc.submit(req()); assert result.status == "FILLED"; assert lifecycle.orders["L-1"].status == OrderStatus.FILLED; assert lifecycle.positions["NIFTY"].quantity == 1; assert lifecycle.orders["L-1"].broker_account_id == 1; assert lifecycle.orders["L-1"].broker_route == "test"

def test_rejected_broker_result_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "REJECTED"); result = svc.submit(req()); assert result.status == "REJECTED"; assert lifecycle.orders["L-1"].status == OrderStatus.REJECTED

def test_cancelled_broker_result_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "CANCELLED"); result = svc.submit(req()); assert result.status == "CANCELLED"; assert lifecycle.orders["L-1"].status == OrderStatus.CANCELLED

def test_partial_fill_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "PARTIALLY_FILLED"); result = svc.submit(req()); assert result.status == "PARTIALLY_FILLED"; assert lifecycle.orders["L-1"].status == OrderStatus.PARTIALLY_FILLED; assert lifecycle.orders["L-1"].filled_quantity == 0

@pytest.mark.parametrize("status", ["TRANSIT", "PENDING", "OPEN", "ACKNOWLEDGED"])
def test_working_broker_status_maps_to_submitted(tmp_path, status):
    svc, lifecycle = service(tmp_path, status); result = svc.submit(req()); assert result.status == "SUBMITTED"; assert lifecycle.orders["L-1"].status == OrderStatus.SUBMITTED

def test_live_execution_reserves_exposure_after_revalidated_risk(tmp_path):
    class Reservations:
        def get(self, client_order_id): return 1.0
    class Gate:
        def __init__(self): self.reserve_calls = 0; self.release_calls = 0; self.reservations = Reservations()
        def rebuild_from_lifecycle(self, lifecycle): pass
        def evaluate(self, request, snapshot): return RiskDecision(True, "RISK_OK")
        def reserve(self, request, snapshot): self.reserve_calls += 1; return RiskDecision(True, "RISK_OK")
        def release(self, client_order_id): self.release_calls += 1
        def update_after_fill(self, request, filled_quantity, current_position): return RiskDecision(True, "RISK_OK")
    gate = Gate(); provider = lambda request: RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint="A", position_quantity=0, projected_trade_loss=0); svc, lifecycle = service(tmp_path, risk_gate=gate, risk_provider=provider); result = svc.submit(req()); assert result.status == "FILLED"; assert gate.reserve_calls == 1; assert gate.release_calls == 1

def test_recovery_error_after_other_claim_releases_reservation(tmp_path):
    class Gate:
        def __init__(self): self.reservations = type("Reservations", (), {"get": lambda self, _: 1.0})(); self.reserve_calls = 0; self.release_calls = 0
        def rebuild_from_lifecycle(self, lifecycle): pass
        def evaluate(self, request, snapshot): return RiskDecision(True, "RISK_OK")
        def reserve(self, request, snapshot): self.reserve_calls += 1; return RiskDecision(True, "RISK_OK")
        def release(self, client_order_id): self.release_calls += 1
        def update_after_fill(self, request, filled_quantity, current_position): return RiskDecision(True, "RISK_OK")
    gate = Gate(); provider = lambda request: RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint="A", position_quantity=0, projected_trade_loss=0); svc, lifecycle = service(tmp_path, risk_gate=gate, risk_provider=provider); store = IdempotencyStore(str(tmp_path / "claims.json")); store.claim("L-1", "other-execution"); svc.idempotency_store = store; svc.router.find_order_by_client_id = lambda *_: (_ for _ in ()).throw(RuntimeError("broker unavailable")); result = svc.submit(req()); assert result.status == "SUBMITTED"; assert "RECOVERY_ERROR" in result.message; assert gate.reserve_calls == 1; assert gate.release_calls == 1

def test_pre_submission_recovery_error_releases_reservation(tmp_path):
    class Gate:
        def __init__(self): self.reservations = type("Reservations", (), {"get": lambda self, _: 1.0})(); self.reserve_calls = 0; self.release_calls = 0
        def rebuild_from_lifecycle(self, lifecycle): pass
        def evaluate(self, request, snapshot): return RiskDecision(True, "RISK_OK")
        def reserve(self, request, snapshot): self.reserve_calls += 1; return RiskDecision(True, "RISK_OK")
        def release(self, client_order_id): self.release_calls += 1
        def update_after_fill(self, request, filled_quantity, current_position): return RiskDecision(True, "RISK_OK")
    gate = Gate(); provider = lambda request: RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint="A", position_quantity=0, projected_trade_loss=0); svc, lifecycle = service(tmp_path, risk_gate=gate, risk_provider=provider); svc.router.find_order_by_client_id = lambda *_: (_ for _ in ()).throw(RuntimeError("broker unavailable")); result = svc.submit(req()); assert result.status == "SUBMITTED"; assert "PRE_SUBMISSION_FAILURE" in result.message; assert gate.reserve_calls == 1; assert gate.release_calls == 1

def test_execution_metrics_are_scoped_to_broker_account(tmp_path):
    from app.execution_observability import ExecutionObservability
    metrics = ExecutionObservability()
    svc, lifecycle = service(tmp_path, observability=metrics)
    result = svc.submit(req())
    assert result.status == "FILLED"
    aggregate = metrics.snapshot()
    scoped = metrics.snapshot_scoped(1, "test")
    assert aggregate.submissions == 1
    assert aggregate.submitted == 1
    assert scoped.submissions == 1
    assert scoped.submitted == 1
    assert scoped.broker_failures == 0
    assert scoped.broker_latency_samples == 1
    assert scoped.recovery_latency_samples >= 1

def test_metrics_failures_never_change_execution_result(tmp_path):
    class BrokenMetrics:
        def __getattr__(self, name):
            def fail(*args, **kwargs): raise RuntimeError("metrics unavailable")
            return fail
    svc, lifecycle = service(tmp_path, observability=BrokenMetrics())
    result = svc.submit(req())
    assert result.status == "FILLED"
    assert lifecycle.orders["L-1"].status == OrderStatus.FILLED
