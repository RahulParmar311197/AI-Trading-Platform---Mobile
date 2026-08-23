from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.execution_persistence import ExecutionStateStore


def test_execution_state_round_trip(tmp_path):
    path = tmp_path / "execution.json"
    source = OrderLifecycle()
    source.create("o1", "NIFTY", "BUY", 10)
    source.transition("o1", OrderStatus.FILLED, 10, 100.0)
    store = ExecutionStateStore(str(path))
    store.save(source)

    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.orders["o1"].status == OrderStatus.FILLED
    assert restored.orders["o1"].filled_quantity == 10
    assert restored.orders["o1"].applied_fill_quantity == 10
    assert restored.orders["o1"].applied_fill_value == 1000
    assert restored.positions["NIFTY"].quantity == 10


def test_partial_fill_restart_does_not_double_count_reconciliation(tmp_path):
    path = tmp_path / "execution.json"
    source = OrderLifecycle()
    source.create("o1", "NIFTY", "BUY", 10)
    source.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 100.0)
    store = ExecutionStateStore(str(path))
    store.save(source)

    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.orders["o1"].applied_fill_quantity == 4
    assert restored.positions["NIFTY"].quantity == 4

    # Broker reconciliation reports the final cumulative fill. Only 6 new units apply.
    restored.transition("o1", OrderStatus.FILLED, 10, 102.0)
    assert restored.orders["o1"].applied_fill_quantity == 10
    assert restored.positions["NIFTY"].quantity == 10

    # Reconciliation replay after restart remains idempotent.
    store.save(restored)
    again = OrderLifecycle()
    assert store.load(again)
    again.transition("o1", OrderStatus.FILLED, 10, 102.0)
    assert again.positions["NIFTY"].quantity == 10


def test_missing_state_returns_false(tmp_path):
    assert not ExecutionStateStore(str(tmp_path / "missing.json")).load(OrderLifecycle())
