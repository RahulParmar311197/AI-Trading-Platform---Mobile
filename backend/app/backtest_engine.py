from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

from app.strategy import generate_signal
from app.market_data import Candle


@dataclass
class BacktestTrade:
    side: str
    entry: float
    exit: float
    pnl: float
    bars: int
    reason: str


def run_backtest(candles: list[Candle], starting_equity: float = 100000.0, risk_percent: float = 1.0) -> dict:
    if starting_equity <= 0 or risk_percent <= 0 or len(candles) < 25:
        raise ValueError("invalid capital/risk or insufficient candles")
    equity = starting_equity
    peak = equity
    max_drawdown = 0.0
    trades: list[BacktestTrade] = []
    returns: list[float] = []
    i = 20
    while i < len(candles) - 1:
        signal = generate_signal(candles[: i + 1])
        if signal is None:
            i += 1
            continue
        risk_amount = equity * risk_percent / 100
        per_unit_risk = abs(signal.entry - signal.stop_loss)
        quantity = risk_amount / per_unit_risk if per_unit_risk else 0
        if quantity <= 0:
            i += 1
            continue
        exit_price = candles[i].close
        reason = "end_of_test"
        bars = 0
        for j in range(i + 1, len(candles)):
            bars += 1
            bar = candles[j]
            if signal.action == "BUY":
                if bar.low <= signal.stop_loss:
                    exit_price, reason = signal.stop_loss, "stop_loss"
                    i = j
                    break
                if bar.high >= signal.target:
                    exit_price, reason = signal.target, "target"
                    i = j
                    break
            else:
                if bar.high >= signal.stop_loss:
                    exit_price, reason = signal.stop_loss, "stop_loss"
                    i = j
                    break
                if bar.low <= signal.target:
                    exit_price, reason = signal.target, "target"
                    i = j
                    break
            exit_price = bar.close
            i = j
        direction = 1 if signal.action == "BUY" else -1
        pnl = (exit_price - signal.entry) * quantity * direction
        equity += pnl
        returns.append(pnl / max(equity - pnl, 1e-9))
        trades.append(BacktestTrade(signal.action, signal.entry, exit_price, pnl, bars, reason))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0)
        i += 1
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    avg_ret = mean(returns) if returns else 0.0
    sd_ret = pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = (avg_ret / sd_ret) * (len(returns) ** 0.5) if sd_ret else 0.0
    return {
        "starting_equity": starting_equity,
        "ending_equity": equity,
        "net_pnl": equity - starting_equity,
        "return_percent": (equity / starting_equity - 1) * 100,
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "max_drawdown_percent": max_drawdown * 100,
        "sharpe": sharpe,
        "trade_journal": [t.__dict__ for t in trades],
    }
