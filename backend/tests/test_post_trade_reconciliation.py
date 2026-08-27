from app.broker_reconciliation import BrokerOrderSnapshot, LocalOrderSnapshot, OrderReconciler
from app.post_trade_reconciliation import PostTradeReconciler
from app.safety_state import SafetyStateStore


def _local(status="FILLED", filled=10.0):
    return LocalOrderSnapshot("BRK-1", "NSE:ABC", "BUY", 10.0, filled, status)


def _broker(status="FILLED", filled=10.0):
    return BrokerOrderSnapshot("BRK-1", "NSE:ABC", "BUY", 10.0, filled, status)


def test_matching_post_trade_order_is_clean(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    reconciler = PostTradeReconciler(safety_store=store)

    result = reconciler.reconcile_execution_result(_local(), _broker())

    assert result.matched is True
    assert result.issues == ()
    assert store.load().trading_halted is False


def test_post_trade_drift_halts_trading(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    reconciler = PostTradeReconciler(safety_store=store)

    result = reconciler.reconcile_execution_result(_local(), _broker(filled=7.0))

    assert result.matched is False
    assert result.issues
    state = store.load()
    assert state.trading_halted is True
    assert "post-trade" in state.halt_reason.lower()


def test_order_reconciler_detects_identity_and_status_drift():
    local = {"BRK-1": _local()}
    broker = [_broker(status="CANCELLED")]

    issues = OrderReconciler().reconcile(local, broker)

    assert any(issue.field == "status" for issue in issues)
