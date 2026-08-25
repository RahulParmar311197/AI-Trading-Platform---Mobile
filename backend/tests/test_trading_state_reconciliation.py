from app.trading_state_reconciliation import ReconciliationState, TradingStateReconciliationGuard


def test_clean_state_is_accepted():
    result = TradingStateReconciliationGuard().evaluate(
        ReconciliationState({"NIFTY": 10}, {"NIFTY": 10}, frozenset({"o1"}), frozenset({"o1"}))
    )
    assert result.clean is True


def test_position_drift_is_rejected():
    result = TradingStateReconciliationGuard().evaluate(
        ReconciliationState({"NIFTY": 10}, {"NIFTY": 15}, frozenset(), frozenset())
    )
    assert result.clean is False
    assert result.position_differences == ("NIFTY",)


def test_order_drift_is_rejected():
    result = TradingStateReconciliationGuard().evaluate(
        ReconciliationState({}, {}, frozenset({"internal-1"}), frozenset({"broker-1"}))
    )
    assert result.clean is False
    assert result.missing_internal_orders == ("broker-1",)
    assert result.missing_broker_orders == ("internal-1",)
