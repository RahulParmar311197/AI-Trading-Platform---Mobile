from types import SimpleNamespace

import pytest

from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator


def _lifecycle(*orders):
    return SimpleNamespace(orders={order.order_id: order for order in orders}, positions={})


def _order(order_id, broker_order_id, status="SUBMITTED"):
    return SimpleNamespace(
        order_id=order_id,
        broker_order_id=broker_order_id,
        status=status,
    )


def test_compare_live_orders_returns_unexplained_active_broker_orders():
    lifecycle = _lifecycle(_order("local-1", "BRK-1"))

    assert StartupRecoveryCoordinator.compare_live_orders(
        lifecycle,
        [
            {"order_id": "BRK-1", "status": "FILLED"},
            {"order_id": "BRK-2", "status": "OPEN"},
        ],
    ) == ("BRK-2",)


def test_compare_live_orders_rejects_duplicate_broker_order_identity():
    lifecycle = _lifecycle(_order("local-1", "BRK-1"))

    with pytest.raises(ValueError, match="duplicate broker order identity"):
        StartupRecoveryCoordinator.compare_live_orders(
            lifecycle,
            [
                {"order_id": "BRK-1", "status": "OPEN"},
                {"order_id": "BRK-1", "status": "OPEN"},
            ],
        )


def test_compare_live_orders_requires_local_broker_identity_for_live_orders():
    lifecycle = _lifecycle(_order("local-1", ""))

    with pytest.raises(ValueError, match="missing broker_order_id"):
        StartupRecoveryCoordinator.compare_live_orders(
            lifecycle,
            [{"order_id": "BRK-1", "status": "OPEN"}],
        )


def test_recover_fails_closed_on_broker_only_live_order():
    lifecycle = _lifecycle(_order("local-1", "BRK-1"))
    coordinator = StartupRecoveryCoordinator()

    result = coordinator.recover(
        lifecycle,
        lambda order: SimpleNamespace(status="FILLED"),
        broker_positions=[],
        broker_orders=[
            {"order_id": "BRK-1", "status": "FILLED"},
            {"order_id": "BRK-2", "status": "OPEN"},
        ],
    )

    assert result.state is RecoveryState.FAILED
    assert result.reason == "broker-only live orders"
    assert result.unresolved_order_ids == ("BRK-2",)
    assert coordinator.execution_allowed is False
