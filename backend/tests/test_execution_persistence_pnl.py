from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_realized_pnl_survives_restart(tmp_path):
    path = tmp_path / "execution_state.json"
    lifecycle = OrderLifecycle()
    lifecycle.create("buy", "NIFTY", "BUY", 10)
    lifecycle.transition("buy", OrderStatus.FILLED, 10, 100)
    lifecycle.create("sell", "NIFTY", "SELL", 10)
    lifecycle.transition("sell", OrderStatus.FILLED, 10, 110)

    assert lifecycle.realized_pnl_by_symbol["NIFTY"] == 100
    ExecutionStateStore(str(path)).save(lifecycle)

    restored = OrderLifecycle()
    assert ExecutionStateStore(str(path)).load(restored)
    assert restored.realized_pnl_by_symbol == {"NIFTY": 100.0}
    assert restored.positions == {}


def test_legacy_state_without_pnl_ledger_loads_cleanly(tmp_path):
    path = tmp_path / "execution_state.json"
    path.write_text('{"orders": {}, "positions": {}}', encoding="utf-8")

    lifecycle = OrderLifecycle()
    assert ExecutionStateStore(str(path)).load(lifecycle)
    assert lifecycle.realized_pnl_by_symbol == {}


def test_invalid_pnl_ledger_fails_closed(tmp_path):
    path = tmp_path / "execution_state.json"
    path.write_text(
        '{"orders": {}, "positions": {}, "realized_pnl_by_symbol": {"NIFTY": "not-a-number"}}',
        encoding="utf-8",
    )

    lifecycle = OrderLifecycle()
    try:
        ExecutionStateStore(str(path)).load(lifecycle)
    except RuntimeError:
        pass
    else:
        raise AssertionError("corrupt P&L state must fail closed")
