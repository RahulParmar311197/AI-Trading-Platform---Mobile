from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.market_data import Candle
from app.strategy import TradeSignal, generate_signal


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 100000.0
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    signal_min_score: int = 2
    freshness_seconds: float | None = None


@dataclass(frozen=True)
class BacktestTrade:
    timestamp: datetime
    action: str
    quantity: float
    signal_price: float
    fill_price: float
    fees: float
    pnl: float


@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    final_equity: float
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[float, ...]

    @property
    def net_pnl(self) -> float:
        return self.final_equity - self.initial_equity


class CandleBacktester:
    """Deterministic strategy replay; never calls live broker/execution services."""
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        if self.config.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.config.fee_bps < 0 or self.config.slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")

    def run(self, candles: list[Candle]) -> BacktestResult:
        if not candles:
            return BacktestResult(self.config.initial_equity, self.config.initial_equity, (), (self.config.initial_equity,))
        ordered = sorted(candles, key=lambda c: c.timestamp)
        equity = self.config.initial_equity
        trades: list[BacktestTrade] = []
        curve = [equity]
        position_side: str | None = None
        entry = 0.0
        quantity = 0.0

        for i in range(20, len(ordered)):
            history = ordered[: i + 1]
            signal: TradeSignal | None = generate_signal(
                history,
                min_score=self.config.signal_min_score,
                max_age_seconds=self.config.freshness_seconds,
                now=ordered[i].timestamp,
            )
            if signal is None:
                curve.append(equity)
                continue
            price = signal.entry
            if position_side == signal.action:
                curve.append(equity)
                continue
            if position_side is not None:
                exit_price = self._fill_price(price, "SELL" if position_side == "BUY" else "BUY")
                pnl = (exit_price - entry) * quantity * (1 if position_side == "BUY" else -1)
                fee = abs(exit_price * quantity) * self.config.fee_bps / 10000
                equity += pnl - fee
                trades.append(BacktestTrade(ordered[i].timestamp, "SELL" if position_side == "BUY" else "BUY", quantity, price, exit_price, fee, pnl - fee))
                position_side = None
                quantity = 0.0
            position_side = signal.action
            quantity = max(1.0, equity / max(price, 1e-12) * 0.01)
            entry = self._fill_price(price, position_side)
            fee = abs(entry * quantity) * self.config.fee_bps / 10000
            equity -= fee
            trades.append(BacktestTrade(ordered[i].timestamp, position_side, quantity, price, entry, fee, -fee))
            curve.append(equity)

        if position_side is not None:
            last = ordered[-1]
            exit_side = "SELL" if position_side == "BUY" else "BUY"
            exit_price = self._fill_price(last.close, exit_side)
            pnl = (exit_price - entry) * quantity * (1 if position_side == "BUY" else -1)
            fee = abs(exit_price * quantity) * self.config.fee_bps / 10000
            equity += pnl - fee
            trades.append(BacktestTrade(last.timestamp, exit_side, quantity, last.close, exit_price, fee, pnl - fee))
            curve.append(equity)
        return BacktestResult(self.config.initial_equity, equity, tuple(trades), tuple(curve))

    def _fill_price(self, price: float, side: str) -> float:
        slip = self.config.slippage_bps / 10000
        return price * (1 + slip if side == "BUY" else 1 - slip)
