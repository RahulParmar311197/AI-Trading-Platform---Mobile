from app.live_execution_repository_bridge import LiveExecutionRepositoryBridge
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_bridge_routes_lifecycle_events(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    bridge = LiveExecutionRepositoryBridge(repo)
    order = bridge.create_order(symbol="NIFTY", side="BUY", quantity=10)
    assert bridge.submitted(event_id="submit-1", order_id=order.order_id) is True
    assert bridge.fill(event_id="fill-1", order_id=order.order_id, quantity=4, price=1000) is True
    assert bridge.fill(event_id="fill-1", order_id=order.order_id, quantity=4, price=1000) is False
    state = bridge.state()
    assert state.positions == {"NIFTY": 4.0}
    assert order.order_id in state.open_order_ids
    repo.close()
