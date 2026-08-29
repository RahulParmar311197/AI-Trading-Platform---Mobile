import pytest

from app.execution_lifecycle import OrderStatus
from app.live_execution_repository_bridge import LiveExecutionRepositoryBridge
from app.transactional_execution_repository import TransactionalExecutionRepository


def make_bridge(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    return repo, LiveExecutionRepositoryBridge(repo)


def test_bridge_routes_lifecycle_events_through_ordered_broker_path(tmp_path):
    repo, bridge = make_bridge(tmp_path)
    try:
        order = bridge.create_order(
            symbol="NIFTY",
            side="BUY",
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
        )
        assert bridge.submitted(
            event_id="submit-1",
            order_id=order.order_id,
            broker_account_id=7,
            broker_route="upstox:account:7",
            event_sequence=10,
        ) is True
        assert bridge.fill(
            event_id="fill-1",
            order_id=order.order_id,
            quantity=4,
            broker_account_id=7,
            broker_route="upstox:account:7",
            price=1000,
            event_sequence=11,
        ) is True
        assert bridge.fill(
            event_id="fill-1",
            order_id=order.order_id,
            quantity=4,
            broker_account_id=7,
            broker_route="upstox:account:7",
            price=1000,
            event_sequence=11,
        ) is False
        state = bridge.state()
        assert state.positions == {(7, "upstox:account:7", "NIFTY"): 4.0}
        assert order.order_id in state.open_order_ids
    finally:
        repo.close()


@pytest.mark.parametrize("method_name", ["submitted", "fill", "cancelled", "rejected"])
def test_bridge_requires_broker_event_sequence(tmp_path, method_name):
    repo, bridge = make_bridge(tmp_path)
    try:
        order = bridge.create_order(
            symbol="NIFTY",
            side="BUY",
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
        )
        kwargs = {
            "event_id": "event-1",
            "order_id": order.order_id,
            "broker_account_id": 7,
            "broker_route": "upstox:account:7",
        }
        if method_name == "fill":
            kwargs.update(quantity=1, price=1000)
        with pytest.raises(TypeError):
            getattr(bridge, method_name)(**kwargs)
        assert repo.get_order(order.order_id)["filled_quantity"] == 0
    finally:
        repo.close()


def test_bridge_rejects_stale_event_without_mutating_state(tmp_path):
    repo, bridge = make_bridge(tmp_path)
    try:
        order = bridge.create_order(
            symbol="NIFTY",
            side="BUY",
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
        )
        bridge.submitted(
            event_id="submit-10",
            order_id=order.order_id,
            broker_account_id=7,
            broker_route="upstox:account:7",
            event_sequence=10,
        )
        bridge.fill(
            event_id="fill-11",
            order_id=order.order_id,
            quantity=4,
            broker_account_id=7,
            broker_route="upstox:account:7",
            price=1000,
            event_sequence=11,
        )
        with pytest.raises(ValueError, match="stale execution event sequence"):
            bridge.fill(
                event_id="fill-9",
                order_id=order.order_id,
                quantity=1,
                broker_account_id=7,
                broker_route="upstox:account:7",
                price=1000,
                event_sequence=9,
            )
        assert repo.get_order(order.order_id)["filled_quantity"] == 4
        assert repo.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 4.0}
    finally:
        repo.close()


@pytest.mark.parametrize(
    ("method_name", "event_sequence", "expected_status"),
    [
        ("submitted", 10, OrderStatus.SUBMITTED.value),
        ("rejected", 10, OrderStatus.REJECTED.value),
    ],
)
def test_terminal_or_invalid_lifecycle_is_not_overwritten(tmp_path, method_name, event_sequence, expected_status):
    repo, bridge = make_bridge(tmp_path)
    try:
        order = bridge.create_order(
            symbol="NIFTY",
            side="BUY",
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
        )
        getattr(bridge, method_name)(
            event_id=f"event-{method_name}",
            order_id=order.order_id,
            broker_account_id=7,
            broker_route="upstox:account:7",
            event_sequence=event_sequence,
        )
        with pytest.raises(ValueError, match="invalid live execution transition"):
            bridge.submitted(
                event_id="late-submitted",
                order_id=order.order_id,
                broker_account_id=7,
                broker_route="upstox:account:7",
                event_sequence=event_sequence + 1,
            )
        assert repo.get_order(order.order_id)["status"] == expected_status
    finally:
        repo.close()


def test_live_fill_after_filled_is_rejected_without_position_change(tmp_path):
    repo, bridge = make_bridge(tmp_path)
    try:
        order = bridge.create_order(
            symbol="NIFTY",
            side="BUY",
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
        )
        bridge.submitted(
            event_id="submit-1",
            order_id=order.order_id,
            broker_account_id=7,
            broker_route="upstox:account:7",
            event_sequence=1,
        )
        bridge.fill(
            event_id="fill-2",
            order_id=order.order_id,
            quantity=10,
            broker_account_id=7,
            broker_route="upstox:account:7",
            price=1000,
            event_sequence=2,
        )
        with pytest.raises(ValueError, match="invalid live execution transition"):
            bridge.fill(
                event_id="late-fill",
                order_id=order.order_id,
                quantity=1,
                broker_account_id=7,
                broker_route="upstox:account:7",
                price=1001,
                event_sequence=3,
            )
        assert repo.get_order(order.order_id)["filled_quantity"] == 10
        assert repo.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 10.0}
    finally:
        repo.close()
