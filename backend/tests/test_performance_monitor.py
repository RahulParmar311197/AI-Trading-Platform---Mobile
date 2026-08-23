from app.performance_monitor import LivePerformanceMonitor


def test_monitor_builds_snapshot_and_drift():
    baseline={'win_rate':0.5,'profit_factor':1.0,'expectancy':10,'max_drawdown':0.2,'trade_count':20}
    monitor=LivePerformanceMonitor(baseline,window_size=30)
    equity=10000
    for pnl in [100,-50,80,70,-20,60]:
        equity += pnl
        monitor.record_trade(pnl,equity)
    snapshot=monitor.snapshot()
    assert snapshot.metrics['trade_count']==6
    assert 'drift' not in snapshot.metrics
    assert snapshot.drift is not None


def test_empty_monitor_is_warning():
    monitor=LivePerformanceMonitor({'win_rate':0.5,'profit_factor':1.0,'expectancy':10,'max_drawdown':0.2})
    snapshot=monitor.snapshot()
    assert snapshot.drift.severity=='WARNING'
    assert 'NO_LIVE_DATA' in snapshot.drift.reasons
