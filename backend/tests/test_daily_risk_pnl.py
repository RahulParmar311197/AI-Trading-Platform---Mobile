from datetime import datetime, timezone

from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import PreTradeRiskGate, RiskLimits


def _closed_trade(lifecycle):
    lifecycle.create("buy-1", "NIFTY", "BUY", 10)
    lifecycle.transition("buy-1", OrderStatus.FILLED, filled_quantity=10, fill_price=100)
    lifecycle.create("sell-1", "NIFTY", "SELL", 10)
    lifecycle.transition("sell-1", OrderStatus.FILLED, filled_quantity=10, fill_price=90)


def test_realized_loss_is_recorded_by_day():
    lifecycle = OrderLifecycle()
    _closed_trade(lifecycle)
    assert sum(lifecycle.realized_pnl_by_symbol.values()) == -100
    assert sum(lifecycle.realized_pnl_by_day.values()) == -100
    today = datetime.now(timezone.utc).date().isoformat()
    assert lifecycle.realized_pnl_by_day[today] == -100


def test_daily_pnl_survives_restart_and_blocks_new_risk(tmp_path):
    lifecycle = OrderLifecycle()
    _closed_trade(lifecycle)
    store = ExecutionStateStore(str(tmp_path / "execution.json"))
    store.save(lifecycle)

    restored = OrderLifecycle()
    assert store.load(restored)
    gate = PreTradeRiskGate(RiskLimits(10, 20, 100, 1000))
    today = datetime.now(timezone.utc).date().isoformat()
    snapshot = gate.snapshot_from_lifecycle(restored, position_quantity=0, broker_ready=True, trading_day=today)
    assert snapshot.daily_pnl == -100
    decision = gate.evaluate(
        type("Request", (), {"quantity": 1, "side": "BUY"})(),
        snapshot,
    )
    assert not decision.allowed
    assert decision.reason == "RISK_DAILY_LOSS_LIMIT"


def test_old_state_without_daily_ledger_remains_compatible(tmp_path):
    store = ExecutionStateStore(str(tmp_path / "execution.json"))
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text('{"orders": {}, "positions": {}, "realized_pnl_by_symbol": {"NIFTY": -50}}', encoding="utf-8")
    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.realized_pnl_by_day == {}
