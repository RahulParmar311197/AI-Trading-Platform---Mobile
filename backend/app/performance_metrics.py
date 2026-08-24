from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Sequence

from app.backtest_engine import BacktestResult, BacktestTrade


@dataclass(frozen=True)
class PerformanceMetrics:
    net_pnl: float
    return_pct: float
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    average_win: float
    average_loss: float
    consecutive_wins: int
    consecutive_losses: int
    trade_count: int


class PerformanceAnalyzer:
    """Calculates risk-aware performance metrics from closed backtest trades."""

    @staticmethod
    def _returns(result: BacktestResult) -> list[float]:
        equity = result.initial_equity
        values=[]
        for trade in result.trades:
            previous=equity
            equity += trade.net_pnl
            values.append(trade.net_pnl / previous if previous else 0.0)
        return values

    def analyze(self, result: BacktestResult) -> PerformanceMetrics:
        trades: Sequence[BacktestTrade] = result.trades
        pnls=[t.net_pnl for t in trades]
        wins=[p for p in pnls if p > 0]
        losses=[p for p in pnls if p < 0]
        gross_profit=sum(wins); gross_loss=abs(sum(losses))
        equity=result.initial_equity; peak=equity; max_dd=0.0
        for pnl in pnls:
            equity += pnl
            peak=max(peak,equity)
            max_dd=max(max_dd,peak-equity)
        dd_pct=max_dd/result.initial_equity if result.initial_equity else 0.0
        returns=self._returns(result)
        avg=mean(returns) if returns else 0.0
        downside=[min(0.0,r) for r in returns]
        variance=mean([(r-avg)**2 for r in returns]) if returns else 0.0
        downside_dev=sqrt(mean([r*r for r in downside])) if returns else 0.0
        sharpe=(avg/sqrt(variance))*sqrt(len(returns)) if variance > 0 else 0.0
        sortino=(avg/downside_dev)*sqrt(len(returns)) if downside_dev > 0 else 0.0
        max_w=max_l=cur_w=cur_l=0
        for p in pnls:
            if p>0: cur_w+=1; cur_l=0; max_w=max(max_w,cur_w)
            elif p<0: cur_l+=1; cur_w=0; max_l=max(max_l,cur_l)
            else: cur_w=cur_l=0
        return PerformanceMetrics(
            net_pnl=result.net_pnl,
            return_pct=(result.net_pnl/result.initial_equity) if result.initial_equity else 0.0,
            win_rate=(len(wins)/len(pnls)) if pnls else 0.0,
            profit_factor=(gross_profit/gross_loss) if gross_loss else (float('inf') if gross_profit else 0.0),
            expectancy=mean(pnls) if pnls else 0.0,
            max_drawdown=max_dd,
            max_drawdown_pct=dd_pct,
            sharpe=sharpe,
            sortino=sortino,
            average_win=mean(wins) if wins else 0.0,
            average_loss=mean(losses) if losses else 0.0,
            consecutive_wins=max_w,
            consecutive_losses=max_l,
            trade_count=len(pnls),
        )
