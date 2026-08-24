from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle


def test_execution_id_survives_save_and_load(tmp_path):
    store = ExecutionStateStore(str(tmp_path / 'execution.json'))
    lifecycle = OrderLifecycle()
    lifecycle.create('OID-1', 'NIFTY', 'BUY', 1, execution_id='EXEC-123')
    store.save(lifecycle)

    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.orders['OID-1'].execution_id == 'EXEC-123'
