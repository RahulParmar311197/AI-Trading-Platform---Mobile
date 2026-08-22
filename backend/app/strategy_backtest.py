from __future__ import annotations

from dataclasses import dataclass
from app.ensemble import decide
from app.ml_metrics import trading_metrics
from app.market_data import Candle

@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    risk_per_trade: float = 0.01
    fee_bps: float = 3.0
    slippage_bps: float = 1.0
    stop_atr: float = 1.5
    target_atr: float = 3.0
    min_confidence: float = 0.35


def run_strategy_backtest(candles: list[Candle], config: BacktestConfig) -> dict:
    if len(candles) < 40: raise ValueError("at least 40 candles required")
    capital = config.initial_capital
    equity_curve = [capital]
    returns: list[float] = []
    trades = []
    position = None
    for i in range(35, len(candles)):
        c = candles[i]
        if position:
            direction = position["direction"]
            hit_stop = c.low <= position["stop"] if direction == 1 else c.high >= position["stop"]
            hit_target = c.high >= position["target"] if direction == 1 else c.low <= position["target"]
            if hit_stop or hit_target:
                exit_price = position["stop"] if hit_stop else position["target"]
                pnl = (exit_price - position["entry"]) * position["qty"] * direction
                costs = (abs(position["entry"] * position["qty"]) + abs(exit_price * position["qty"])) * (config.fee_bps + config.slippage_bps) / 10000
                pnl -= costs
                ret = pnl / capital
                capital += pnl
                returns.append(ret); equity_curve.append(capital)
                trades.append({"entry": position["entry"], "exit": exit_price, "direction": direction, "pnl": pnl, "reason": "STOP" if hit_stop else "TARGET"})
                position = None
            continue
        result = decide(candles[max(0, i-200):i+1])
        if result.action == "NO_TRADE" or result.confidence < config.min_confidence: continue
        atr = max(c.high - c.low, 0.000001)
        direction = 1 if result.action == "BUY" else -1
        stop_distance = atr * config.stop_atr
        qty = (capital * config.risk_per_trade) / stop_distance
        entry = c.close * (1 + direction * config.slippage_bps / 10000)
        position = {"entry": entry, "qty": qty, "direction": direction, "stop": entry - direction * stop_distance, "target": entry + direction * atr * config.target_atr}
    return {"config": config.__dict__, "trades": trades, "metrics": trading_metrics(returns), "equity_curve": equity_curve, "open_position": position}
