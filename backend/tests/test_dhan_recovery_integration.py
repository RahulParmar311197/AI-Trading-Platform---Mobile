from app.dhan_adapter import DhanAdapter, DhanConfig
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.recovery_manager import StartupRecoveryManager
from app.safety_state import SafetyStateStore


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeTransport:
    def get(self, url, headers):
        if url.endswith("/orders"):
            return FakeResponse([{"orderId": "D-1", "correlationId": "local-1", "orderStatus": "TRADED"}])
        if url.endswith("/positions"):
            return FakeResponse([{"tradingSymbol": "NIFTY", "netQty": 10}])
        raise AssertionError(url)


def test_dhan_snapshot_can_drive_verified_startup_recovery(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10)
    lifecycle.transition("local-1", OrderStatus.FILLED, 10, 100)
    ExecutionStateStore(str(tmp_path / "execution.json")).save(lifecycle)

    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), FakeTransport())
    manager = StartupRecoveryManager(
        ExecutionStateStore(str(tmp_path / "execution.json")),
        SafetyStateStore(str(tmp_path / "safety.json")),
    )

    result = manager.startup(OrderLifecycle(), adapter.get_snapshot)

    assert result.ready is True
    assert result.reason == "RECOVERY_OK"
    assert result.reconciliation is not None
    assert result.reconciliation.ok is True
