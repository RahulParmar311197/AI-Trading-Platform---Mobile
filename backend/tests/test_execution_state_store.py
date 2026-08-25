from app.execution_state_store import ExecutionStateStore


def test_fill_updates_position_and_order_state():
    store = ExecutionStateStore()
    store.register_order(order_id="o1", symbol="NIFTY", side="BUY", quantity=10)
    store.apply_fill(order_id="o1", filled_quantity=6)
    state = store.get_state()
    assert state.positions == {"NIFTY": 6.0}
    assert state.open_order_ids == frozenset({"o1"})
    store.apply_fill(order_id="o1", filled_quantity=4)
    assert store.get_state().positions == {"NIFTY": 10.0}
    store.close_order(order_id="o1")
    assert store.get_state().open_order_ids == frozenset()


def test_sell_fill_reduces_position():
    store = ExecutionStateStore()
    store.register_order(order_id="o1", symbol="NIFTY", side="BUY", quantity=10)
    store.apply_fill(order_id="o1", filled_quantity=10)
    store.close_order(order_id="o1")
    store.register_order(order_id="o2", symbol="NIFTY", side="SELL", quantity=3)
    store.apply_fill(order_id="o2", filled_quantity=3)
    assert store.get_state().positions == {"NIFTY": 7.0}
