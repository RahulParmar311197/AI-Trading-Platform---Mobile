from app.ai_performance_analytics import AIPerformanceAnalytics


def test_performance_metrics():
    report = AIPerformanceAnalytics().analyze([{"pnl":100},{"pnl":-50},{"pnl":0},{"pnl":50}])
    assert report.total_trades == 4
    assert report.wins == 2
    assert report.losses == 1
    assert report.breakeven == 1
    assert report.net_pnl == 100
    assert report.expectancy == 25
    assert report.max_drawdown == 50


def test_empty_history_is_safe():
    report = AIPerformanceAnalytics().analyze([])
    assert report.total_trades == 0
    assert report.win_rate == 0
    assert report.expectancy == 0
