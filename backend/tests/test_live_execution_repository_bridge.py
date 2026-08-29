import pytest

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
        bridge.fill(
            event_id="fill-10",
            order_id=order.order_id,
            quantity=4,
            broker_account_id=7,
            broker_route="upstox:account:7",
            price=1000,
            event_sequence=10,
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
