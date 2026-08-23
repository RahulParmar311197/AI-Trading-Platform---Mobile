from app.backtest_analytics import BacktestAnalyticsEngine


def test_metrics():
    r = BacktestAnalyticsEngine().calculate(
        100000,
        [100000, 101000, 100500, 99500, 103000],
        [1000, -500, 2500, -100],
    )
    assert r.trades == 4
    assert r.wins == 2
    assert r.losses == 2
    assert r.win_rate_pct == 50
    assert r.final_equity == 103000
    assert r.max_drawdown_pct > 0
    assert r.largest_win == 2500
    assert r.largest_loss == -500


def test_empty_trades():
    r = BacktestAnalyticsEngine().calculate(100000, [100000], [])
    assert r.trades == 0
    assert r.win_rate_pct == 0
    assert r.expectancy == 0


def test_invalid_inputs():
    try:
        BacktestAnalyticsEngine().calculate(0, [0], [])
        assert False
    except ValueError:
        pass
