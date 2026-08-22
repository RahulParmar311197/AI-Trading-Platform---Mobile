from app.order_lifecycle import OrderLifecycle
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderStatus


def test_execution_state_round_trip(tmp_path):
    path=tmp_path/'execution.json'; source=OrderLifecycle(); source.create('o1','NIFTY','BUY',10); source.transition('o1',OrderStatus.FILLED,10,100.0)
    store=ExecutionStateStore(str(path)); store.save(source)
    restored=OrderLifecycle(); assert store.load(restored)
    assert restored.orders['o1'].status==OrderStatus.FILLED
    assert restored.orders['o1'].filled_quantity==10
    assert restored.positions['NIFTY'].quantity==10


def test_missing_state_returns_false(tmp_path):
    assert not ExecutionStateStore(str(tmp_path/'missing.json')).load(OrderLifecycle())
