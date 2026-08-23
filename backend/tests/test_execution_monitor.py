from app.execution_monitor import ExecutionMonitor
from app.paper_trading_guard import TradingMode
from app.strategy_promotion import PromotionStatus

BASE={'win_rate':0.5,'profit_factor':1.0,'expectancy':10,'max_drawdown':0.2,'trade_count':20}


def test_fill_flows_into_monitor_and_safety():
    monitor=ExecutionMonitor(PromotionStatus.LIVE_ELIGIBLE,BASE,window_size=50)
    equity=10000
    for pnl in [100,80,-30,90]:
        equity+=pnl
        monitor.record_fill(pnl,equity)
    snapshot,decision=monitor.evaluate()
    assert snapshot.metrics['trade_count']==4
    assert decision.mode==TradingMode.LIVE
    assert not decision.paused


def test_consecutive_losses_reach_safety_controller():
    monitor=ExecutionMonitor(PromotionStatus.LIVE_ELIGIBLE,BASE,window_size=50)
    equity=10000
    for pnl in [-10,-10,-10,-10,-10]:
        equity+=pnl
        monitor.record_fill(pnl,equity)
    _,decision=monitor.evaluate()
    assert decision.paused
    assert 'CONSECUTIVE_LOSS_LIMIT' in decision.reasons
