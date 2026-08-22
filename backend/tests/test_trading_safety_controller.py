from app.trading_safety_controller import evaluate_safety
from app.paper_trading_guard import TradingMode
from app.strategy_drift import DriftResult
from app.strategy_promotion import PromotionStatus


def test_normal_stays_live():
    drift=DriftResult(False,'NORMAL',(),0)
    result=evaluate_safety(PromotionStatus.LIVE_ELIGIBLE,100000,100000,100000,0,drift)
    assert result.mode==TradingMode.LIVE and not result.paused


def test_warning_downgrades_live_to_paper():
    drift=DriftResult(True,'WARNING',('WIN_RATE_DRIFT',),20)
    result=evaluate_safety(PromotionStatus.LIVE_ELIGIBLE,100000,100000,100000,0,drift)
    assert result.mode==TradingMode.PAPER and not result.paused
    assert 'STRATEGY_DRIFT_WARNING' in result.reasons


def test_critical_drift_pauses():
    drift=DriftResult(True,'CRITICAL',('DRAWDOWN_DRIFT','EXPECTANCY_DRIFT'),40)
    result=evaluate_safety(PromotionStatus.LIVE_ELIGIBLE,100000,100000,100000,0,drift)
    assert result.mode==TradingMode.DISABLED and result.paused
    assert 'DRAWDOWN_DRIFT' in result.reasons
