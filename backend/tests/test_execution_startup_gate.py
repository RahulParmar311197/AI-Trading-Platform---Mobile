import pytest

from app.broker_adapter import BrokerOrderRequest
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.execution_persistence import ExecutionStateStore
from app.startup_recovery import StartupRecoveryCoordinator


class RouterStub:
    def __init__(self):
        self.submissions = 0

    def find_order_by_client_id(self, client_order_id):
        return None

    def submit(self, request):
        self.submissions += 1
        raise AssertionError("broker submission must be blocked before recovery")


def make_request():
    return BrokerOrderRequest(client_order_id="test-order", symbol="NIFTY", side="BUY", quantity=1, order_type="MARKET")


def test_submit_is_blocked_until_recovery_ready(tmp_path):
    router = RouterStub()
    lifecycle = OrderLifecycle()
    recovery = StartupRecoveryCoordinator()
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "state.json")), recovery=recovery)

    result = service.submit(make_request())

    assert result.message == "LIVE_EXECUTION_LOCKED_STARTUP_RECOVERY_REQUIRED"
    assert router.submissions == 0
    assert "test-order" not in lifecycle.orders


def test_submit_reaches_broker_after_recovery_ready(tmp_path):
    class ReadyRouter(RouterStub):
        def submit(self, request):
            self.submissions += 1
            return type("Result", (), {"status": "REJECTED", "order_id": "broker-1", "price": None})()

    router = ReadyRouter()
    lifecycle = OrderLifecycle()
    recovery = StartupRecoveryCoordinator()
    recovery.begin()
    recovery.state = recovery.state.READY
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "state.json")), recovery=recovery)

    result = service.submit(make_request())

    assert result.status == OrderStatus.REJECTED.value
    assert router.submissions == 1
