from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean, pstdev
from typing import Sequence


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    gross_profit: float
    gross_loss: float
    net_pnl: float


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    value = numerator / denominator
    return value if math.isfinite(value) else 0.0


def calculate_performance_metrics(
    equity_curve: Sequence[float],
    trade_pnls: Sequence[float] = (),
    *,
    initial_equity: float | None = None,
    periods_per_year: float = 252.0,
) -> PerformanceMetrics:
    values = [float(v) for v in equity_curve]
    if not values:
        return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0.0, 0.0, 0.0)
    if periods_per_year <= 0:
        raise ValueError('periods_per_year must be positive')
    initial = float(initial_equity if initial_equity is not None else values[0])
    final = values[-1]
    total_return = _safe_ratio(final - initial, initial)
    trades = [float(p) for p in trade_pnls]
    winners = [p for p in trades if p > 0]
    losers = [p for p in trades if p < 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    peak = values[0]
    max_dd = max_dd_pct = 0.0
    for value in values:
        peak = max(peak, value)
        dd = peak - value
        max_dd = max(max_dd, dd)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, dd / peak)
    returns = [_safe_ratio(values[i], values[i - 1]) - 1.0 for i in range(1, len(values)) if values[i - 1] != 0]
    std = pstdev(returns) if len(returns) > 1 else 0.0
    volatility = std * math.sqrt(periods_per_year)
    avg_return = mean(returns) if returns else 0.0
    downside_dev = math.sqrt(mean([min(r, 0.0) ** 2 for r in returns])) if returns else 0.0
    sharpe = _safe_ratio(avg_return * math.sqrt(periods_per_year), std)
    sortino = _safe_ratio(avg_return * math.sqrt(periods_per_year), downside_dev)
    return PerformanceMetrics(
        total_return=total_return,
        win_rate=_safe_ratio(len(winners), len(trades)),
        profit_factor=_safe_ratio(gross_profit, gross_loss),
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=_safe_ratio(total_return, max_dd_pct),
        volatility=volatility,
        trade_count=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_pnl=sum(trades),
    )
