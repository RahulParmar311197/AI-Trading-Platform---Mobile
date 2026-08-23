from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.recovery_manager import StartupRecoveryManager
from app.safety_state import SafetyStateStore


def make_manager(tmp_path):
    return StartupRecoveryManager(
        ExecutionStateStore(str(tmp_path / "execution.json")),
        SafetyStateStore(str(tmp_path / "safety.json")),
    )


def test_matching_broker_state_allows_startup(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.transition("o1", OrderStatus.FILLED, 10, 100)
    store = ExecutionStateStore(str(tmp_path / "execution.json"))
    store.save(lifecycle)

    manager = make_manager(tmp_path)
    result = manager.startup(
        OrderLifecycle(),
        lambda: ([{"client_order_id": "o1", "status": "FILLED"}], [{"symbol": "NIFTY", "quantity": 10}]),
    )
    assert result.ready
    assert result.reason == "RECOVERY_OK"
    assert not manager.trading_halted


def test_drift_halts_startup(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.transition("o1", OrderStatus.FILLED, 10, 100)
    ExecutionStateStore(str(tmp_path / "execution.json")).save(lifecycle)

    manager = make_manager(tmp_path)
    result = manager.startup(
        OrderLifecycle(),
        lambda: ([], []),
    )
    assert not result.ready
    assert result.reason == "BROKER_STATE_DRIFT"
    assert manager.trading_halted
    assert SafetyStateStore(str(tmp_path / "safety.json")).load().trading_halted


def test_broker_failure_halts_startup(tmp_path):
    manager = make_manager(tmp_path)

    def fail():
        raise ConnectionError("broker unavailable")

    result = manager.startup(OrderLifecycle(), fail)
    assert not result.ready
    assert result.reason == "RECOVERY_FAILED"
    assert manager.trading_halted


def test_persisted_halt_requires_explicit_resume(tmp_path):
    lifecycle = OrderLifecycle()
    ExecutionStateStore(str(tmp_path / "execution.json")).save(lifecycle)
    SafetyStateStore(str(tmp_path / "safety.json")).halt("MANUAL_HALT")

    manager = make_manager(tmp_path)
    result = manager.startup(lifecycle, lambda: ([], []))
    assert not result.ready
    assert result.reason == "PERSISTED_TRADING_HALT"
    assert manager.trading_halted

    resumed = manager.resume_after_verified_reconciliation()
    assert resumed.ready
    assert not manager.trading_halted
