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

    result = coordinator.recover(
        lifecycle,
        lambda order: order,
        broker_orders=[],
        broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
    )

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

    result = coordinator.recover(
        lifecycle,
        reconcile,
        broker_orders=[],
        broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
    )

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


def test_missing_broker_order_snapshot_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    result = coordinator.recover(
        lifecycle,
        lambda order: order,
        broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
    )

    assert result.state == RecoveryState.FAILED
    assert result.reason == "broker order snapshot unavailable"
    assert not coordinator.execution_allowed


def test_unknown_broker_position_side_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    with pytest.raises(ValueError, match="unknown broker position side"):
        coordinator.recover(
            lifecycle,
            lambda order: order,
            broker_orders=[],
            broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "MYSTERY"}],
        )

    assert coordinator.state == RecoveryState.FAILED
    assert not coordinator.execution_allowed


def test_unknown_local_position_side_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    lifecycle.positions["NIFTY"].side = "MYSTERY"
    coordinator = StartupRecoveryCoordinator()

    with pytest.raises(ValueError, match="unknown local position side"):
        coordinator.recover(
            lifecycle,
            lambda order: order,
            broker_orders=[],
            broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
        )

    assert coordinator.state == RecoveryState.FAILED
    assert not coordinator.execution_allowed


def test_broker_order_missing_status_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    with pytest.raises(ValueError, match="missing status"):
        coordinator.recover(
            lifecycle,
            lambda order: order,
            broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
            broker_orders=[{"order_id": "b1"}],
        )

    assert coordinator.state == RecoveryState.FAILED
    assert not coordinator.execution_allowed


def test_unknown_broker_order_status_fails_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    with pytest.raises(ValueError, match="unknown broker order status"):
        coordinator.recover(
            lifecycle,
            lambda order: order,
            broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
            broker_orders=[{"order_id": "b1", "status": "BROKER_INVENTED_STATE"}],
        )

    assert coordinator.state == RecoveryState.FAILED
    assert not coordinator.execution_allowed


def test_terminal_broker_order_status_is_not_treated_as_live():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    lifecycle.transition("o1", OrderStatus.FILLED, 1, 100.0)
    coordinator = StartupRecoveryCoordinator()

    result = coordinator.recover(
        lifecycle,
        lambda order: order,
        broker_positions=[{"symbol": "NIFTY", "quantity": 1, "side": "BUY"}],
        broker_orders=[{"order_id": "b1", "status": "COMPLETE"}],
    )

    assert result.state == RecoveryState.READY
    assert coordinator.execution_allowed
