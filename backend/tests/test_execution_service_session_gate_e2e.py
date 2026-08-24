from dataclasses import dataclass
from datetime import datetime, timezone

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_authorization import ExecutionAuthorization
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore
from app.session_baseline import SessionBaselineStore
from app.session_risk import SessionPolicy
from app.session_risk_gate import SessionRiskGate


@dataclass(frozen=True)
class Snapshot:
    timestamp: datetime
    current_equity: float
    realized_daily_pnl: float


class Broker:
    def __init__(self): self.submit_calls = 0
    def submit_order(self, request):
        self.submit_calls += 1
        return BrokerOrderUpdate(order_id="B1", status="NEW", client_order_id=request.client_order_id, quantity=request.quantity)
    def cancel_order(self, order_id): return BrokerOrderUpdate(order_id=order_id, status="CANCELLED")
    def get_order(self, order_id): return {}
    def get_positions(self): return []
    def get_account(self): return {}


def request():
    return BrokerOrderRequest(client_order_id="session-loss-1", symbol="NIFTY", side="BUY", quantity=1)


def test_session_loss_blocks_before_broker_router(tmp_path):
    broker = Broker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=SafetyStateStore(str(tmp_path / "safety.json")))
    baseline = SessionBaselineStore(str(tmp_path / "baseline.json"))
    session_gate = SessionRiskGate(baseline, SessionPolicy(block_after_daily_loss_percent=3.0))
    ts = datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc)
    snapshot = Snapshot(ts, 97000, -3000)
    authorization = ExecutionAuthorization(router.safety_store, session_risk_gate=session_gate, session_clock=lambda _: snapshot)
    service = OrderExecutionService(router, OrderLifecycle(), ExecutionStateStore(str(tmp_path / "execution.json")), authorization=authorization)

    result = service.submit(request())

    assert not result.status == "FILLED"
    assert "SESSION_RISK_REJECTED" in (result.message or "")
    assert broker.submit_calls == 0
