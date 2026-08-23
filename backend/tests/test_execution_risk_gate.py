from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot
from app.startup_recovery import StartupRecoveryCoordinator


class RouterStub:
    def __init__(self):
        self.submissions = 0

    def find_order_by_client_id(self, client_order_id):
        return None

    def submit(self, request):
        self.submissions += 1
        return BrokerOrderUpdate(order_id="broker-1", status="FILLED", client_order_id=request.client_order_id, symbol=request.symbol, side=request.side, quantity=request.quantity, price=100)


def make_service(tmp_path, snapshot):
    router = RouterStub()
    recovery = StartupRecoveryCoordinator()
    recovery.begin()
    recovery.state = recovery.state.READY
    gate = PreTradeRiskGate(RiskLimits(max_order_quantity=10, max_position_quantity=20, max_daily_loss=1000, max_trade_loss=200))
    service = OrderExecutionService(
        router,
        OrderLifecycle(),
        ExecutionStateStore(str(tmp_path / "state.json")),
        recovery=recovery,
        risk_gate=gate,
        risk_snapshot_provider=lambda: snapshot,
    )
    return service, router


def request(quantity=5):
    return BrokerOrderRequest(client_order_id="risk-order", symbol="NIFTY", side="BUY", quantity=quantity)


def test_risk_rejection_never_calls_broker(tmp_path):
    service, router = make_service(tmp_path, RiskSnapshot(broker_ready=True, kill_switch=True))
    result = service.submit(request())
    assert result.status == "REJECTED"
    assert result.message == "RISK_KILL_SWITCH_ACTIVE"
    assert router.submissions == 0


def test_risk_limit_rejection_never_calls_broker(tmp_path):
    service, router = make_service(tmp_path, RiskSnapshot(broker_ready=True, position_quantity=18))
    result = service.submit(request(5))
    assert result.status == "REJECTED"
    assert result.message == "RISK_MAX_POSITION_QUANTITY"
    assert router.submissions == 0


def test_risk_provider_failure_fails_closed(tmp_path):
    router = RouterStub()
    recovery = StartupRecoveryCoordinator()
    recovery.begin()
    recovery.state = recovery.state.READY
    gate = PreTradeRiskGate(RiskLimits(10, 20, 1000, 200))
    service = OrderExecutionService(
        router, OrderLifecycle(), ExecutionStateStore(str(tmp_path / "state.json")),
        recovery=recovery, risk_gate=gate, risk_snapshot_provider=lambda: (_ for _ in ()).throw(RuntimeError("snapshot down")),
    )
    result = service.submit(request())
    assert result.status == "REJECTED"
    assert result.message == "RISK_GATE_ERROR"
    assert router.submissions == 0


def test_allowed_risk_reaches_broker(tmp_path):
    service, router = make_service(tmp_path, RiskSnapshot(broker_ready=True))
    result = service.submit(request())
    assert result.status == "FILLED"
    assert router.submissions == 1
