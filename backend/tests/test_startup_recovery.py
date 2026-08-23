import pytest

from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator


def test_execution_is_locked_until_recovery_completes():
    coordinator = StartupRecoveryCoordinator()
    assert coordinator.state == RecoveryState.LOCKED
    with pytest.raises(RuntimeError, match="live execution locked"):
        coordinator.require_execution_ready()


def test_clean_startup_recovery_unlocks_execution():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    result = coordinator.recover(lifecycle, lambda order: order)

    assert result.state == RecoveryState.READY
    assert coordinator.execution_allowed
    coordinator.require_execution_ready()


def test_working_order_blocks_live_execution():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.SUBMITTED)
    coordinator = StartupRecoveryCoordinator()

    result = coordinator.recover(lifecycle, lambda order: order)

    assert result.state == RecoveryState.FAILED
    assert result.unresolved_order_ids == ("o1",)
    assert not coordinator.execution_allowed


def test_reconciled_working_order_can_unlock_execution():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.SUBMITTED)
    coordinator = StartupRecoveryCoordinator()

    def reconcile(order):
        lifecycle.transition(order.order_id, OrderStatus.FILLED, 1, 101.0)
        return lifecycle.orders[order.order_id]

    result = coordinator.recover(lifecycle, reconcile)

    assert result.state == RecoveryState.READY
    assert coordinator.execution_allowed
    assert lifecycle.positions["NIFTY"].quantity == 1


def test_recovery_exception_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.SUBMITTED)
    coordinator = StartupRecoveryCoordinator()

    with pytest.raises(RuntimeError, match="broker unavailable"):
        coordinator.recover(lifecycle, lambda order: (_ for _ in ()).throw(RuntimeError("broker unavailable")))

    assert coordinator.state == RecoveryState.FAILED
    assert not coordinator.execution_allowed
