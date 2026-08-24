from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore
from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator


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
    return BrokerOrderRequest(client_order_id="startup-1", symbol="NIFTY", side="BUY", quantity=1)


def test_locked_recovery_blocks_broker_submission(tmp_path):
    broker = Broker()
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    recovery = StartupRecoveryCoordinator()
    service = OrderExecutionService(router, OrderLifecycle(), ExecutionStateStore(str(tmp_path / "execution.json")), recovery=recovery)

    result = service.submit(request())

    assert result.message == "LIVE_EXECUTION_LOCKED_STARTUP_RECOVERY_REQUIRED"
    assert broker.submit_calls == 0
    assert recovery.state == RecoveryState.LOCKED


def test_unresolved_recovery_keeps_execution_locked(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("pending", "NIFTY", "BUY", 1)
    lifecycle.transition("pending", "SUBMITTED")
    recovery = StartupRecoveryCoordinator()

    result = recovery.recover(lifecycle, lambda order: None)

    assert result.state == RecoveryState.FAILED
    assert not recovery.execution_allowed
    assert result.unresolved_order_ids == ("pending",)
