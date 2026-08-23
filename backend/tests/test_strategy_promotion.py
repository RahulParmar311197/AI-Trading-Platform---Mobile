from app.strategy_promotion import evaluate_strategy_for_promotion, PromotionStatus


def windows():
    return [{'test_metrics':{'net_pnl':1000,'max_drawdown':0.08,'trade_count':40}}, {'test_metrics':{'net_pnl':900,'max_drawdown':0.10,'trade_count':35}}, {'test_metrics':{'net_pnl':1100,'max_drawdown':0.07,'trade_count':45}}]


def test_pass_is_live_eligible():
    result=evaluate_strategy_for_promotion(windows())
    assert result.status==PromotionStatus.LIVE_ELIGIBLE


def test_insufficient_windows_rejected():
    result=evaluate_strategy_for_promotion(windows()[:2],require_oos_windows=3)
    assert result.status==PromotionStatus.REJECT
    assert 'INSUFFICIENT_OOS_WINDOWS' in result.reasons


def test_bad_strategy_not_live_eligible():
    bad=[{'test_metrics':{'net_pnl':100,'max_drawdown':0.40,'trade_count':30}}]*3
    result=evaluate_strategy_for_promotion(bad)
    assert result.status==PromotionStatus.REJECT
