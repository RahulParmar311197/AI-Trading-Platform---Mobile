from app.paper_trading_guard import evaluate_trading_guard, GuardLimits, TradingMode
from app.strategy_promotion import PromotionStatus


def test_live_eligible_can_run_live():
    state=evaluate_trading_guard(PromotionStatus.LIVE_ELIGIBLE,100000,100000,100000,0)
    assert state.mode==TradingMode.LIVE and not state.paused


def test_warning_strategy_is_paper_only():
    state=evaluate_trading_guard(PromotionStatus.PAPER_ONLY,100000,100000,100000,0)
    assert state.mode==TradingMode.PAPER and not state.paused


def test_daily_loss_pauses_trading():
    state=evaluate_trading_guard(PromotionStatus.LIVE_ELIGIBLE,97000,100000,100000,0,GuardLimits(max_daily_loss=0.02))
    assert state.paused and 'DAILY_LOSS_LIMIT' in state.reasons


def test_consecutive_losses_pause():
    state=evaluate_trading_guard(PromotionStatus.LIVE_ELIGIBLE,100000,100000,100000,5)
    assert state.paused and 'CONSECUTIVE_LOSS_LIMIT' in state.reasons
