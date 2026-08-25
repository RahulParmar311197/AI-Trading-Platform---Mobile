from app.live_execution_repository_bridge import LiveExecutionRepositoryBridge
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_bridge_routes_lifecycle_events_with_account_identity(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    bridge = LiveExecutionRepositoryBridge(repo)
    order = bridge.create_order(
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        broker_account_id=7,
        broker_route="upstox:account:7",
    )
    assert order.broker_account_id == 7
    assert order.broker_route == "upstox:account:7"
    assert bridge.submitted(
        event_id="submit-1",
        order_id=order.order_id,
        broker_account_id=7,
        broker_route="upstox:account:7",
    ) is True
    assert bridge.fill(
        event_id="fill-1",
        order_id=order.order_id,
        quantity=4,
        broker_account_id=7,
        broker_route="upstox:account:7",
        price=1000,
    ) is True
    assert bridge.fill(
        event_id="fill-1",
        order_id=order.order_id,
        quantity=4,
        broker_account_id=7,
        broker_route="upstox:account:7",
        price=1000,
    ) is False
    state = bridge.state()
    assert state.positions == {(7, "upstox:account:7", "NIFTY"): 4.0}
    assert order.order_id in state.open_order_ids
    repo.close()
