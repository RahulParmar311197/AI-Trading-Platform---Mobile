from app.performance_metrics import calculate_performance_metrics


def test_metrics_empty_curve_is_zero_safe():
    m = calculate_performance_metrics([])
    assert m.trade_count == 0
    assert m.total_return == 0.0
    assert m.sharpe_ratio == 0.0
    assert m.sortino_ratio == 0.0


def test_metrics_drawdown_and_trade_statistics():
    m = calculate_performance_metrics(
        [100000.0, 102000.0, 98000.0, 105000.0],
        [2000.0, -4000.0, 7000.0],
    )
    assert m.trade_count == 3
    assert m.winning_trades == 2
    assert m.losing_trades == 1
    assert m.gross_profit == 9000.0
    assert m.gross_loss == 4000.0
    assert m.profit_factor == 2.25
    assert m.max_drawdown == 4000.0
    assert m.max_drawdown_pct > 0


def test_metrics_flat_curve_is_finite_and_zero_risk():
    m = calculate_performance_metrics([100000.0] * 5, [0.0])
    assert m.total_return == 0.0
    assert m.volatility == 0.0
    assert m.sharpe_ratio == 0.0
    assert m.sortino_ratio == 0.0
    assert m.calmar_ratio == 0.0
