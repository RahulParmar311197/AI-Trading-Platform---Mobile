from app.robustness import calculate_robustness


def test_robust_strategy_passes():
    windows=[{'test_metrics':{'net_pnl':1000,'max_drawdown':0.08,'trade_count':40}}, {'test_metrics':{'net_pnl':900,'max_drawdown':0.10,'trade_count':35}}, {'test_metrics':{'net_pnl':1100,'max_drawdown':0.07,'trade_count':45}}]
    result=calculate_robustness(windows)
    assert result.status=='PASS'
    assert result.score>=70


def test_bad_drawdown_rejected():
    windows=[{'test_metrics':{'net_pnl':100,'max_drawdown':0.40,'trade_count':30}}]
    result=calculate_robustness(windows)
    assert result.status=='REJECT'
    assert 'EXCESSIVE_DRAWDOWN' in result.reasons


def test_empty_windows_rejected():
    result=calculate_robustness([])
    assert result.status=='REJECT'
