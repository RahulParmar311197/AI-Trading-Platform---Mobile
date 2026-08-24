from app.order_lifecycle import OrderLifecycle
from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator


def test_matching_positions_allow_ready():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("o1", 10, 100, "f1")
    recovery = StartupRecoveryCoordinator()

    result = recovery.recover(lifecycle, lambda order: order, [{"symbol": "NIFTY", "side": "BUY", "quantity": 10}])

    assert result.state == RecoveryState.READY
    assert result.position_mismatches == ()
    assert recovery.execution_allowed


def test_position_mismatch_keeps_execution_locked():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("o1", 10, 100, "f1")
    recovery = StartupRecoveryCoordinator()

    result = recovery.recover(lifecycle, lambda order: order, [{"symbol": "NIFTY", "side": "BUY", "quantity": 9}])

    assert result.state == RecoveryState.FAILED
    assert result.reason == "position reconciliation mismatch"
    assert result.position_mismatches == ("NIFTY: local=10.0 broker=9.0",)
    assert not recovery.execution_allowed


def test_unexpected_broker_position_also_blocks():
    lifecycle = OrderLifecycle()
    recovery = StartupRecoveryCoordinator()

    result = recovery.recover(lifecycle, lambda order: order, [{"symbol": "BANKNIFTY", "side": "SELL", "quantity": 5}])

    assert result.state == RecoveryState.FAILED
    assert result.position_mismatches == ("BANKNIFTY: local=0.0 broker=-5.0",)
