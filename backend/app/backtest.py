from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from app.market_data import Candle, validate_candle_sequence
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
        if not isfinite(float(self.config.initial_equity)) or self.config.initial_equity <= 0:
            raise ValueError("initial_equity must be finite and positive")
        if (
            not isfinite(float(self.config.fee_bps))
            or not isfinite(float(self.config.slippage_bps))
            or self.config.fee_bps < 0
            or self.config.slippage_bps < 0
        ):
            raise ValueError("fee_bps and slippage_bps must be finite and non-negative")
        if isinstance(self.config.signal_min_score, bool) or not isinstance(self.config.signal_min_score, int) or self.config.signal_min_score < 1:
            raise ValueError("signal_min_score must be a positive integer")
        if self.config.freshness_seconds is not None:
            if not isfinite(float(self.config.freshness_seconds)) or self.config.freshness_seconds < 0:
                raise ValueError("freshness_seconds must be finite and non-negative")

    def run(self, candles: list[Candle]) -> BacktestResult:
        if not candles:
            return BacktestResult(self.config.initial_equity, self.config.initial_equity, (), (self.config.initial_equity,))
        if not validate_candle_sequence(candles):
            raise ValueError("candles must be a non-empty canonical monotonic sequence")

        ordered = candles
        equity = float(self.config.initial_equity)
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
            if signal.action not in {"BUY", "SELL"}:
                raise ValueError("strategy returned unsupported backtest action")
            if not all(isfinite(float(value)) for value in (signal.entry, signal.stop_loss, signal.target, signal.risk_reward, signal.confidence)):
                raise ValueError("strategy returned non-finite trade values")
            price = float(signal.entry)
            if price <= 0:
                raise ValueError("strategy returned non-positive entry price")
            if position_side == signal.action:
                curve.append(equity)
                continue
            if position_side is not None:
                exit_side = "SELL" if position_side == "BUY" else "BUY"
                exit_price = self._fill_price(price, exit_side)
                pnl = (exit_price - entry) * quantity * (1 if position_side == "BUY" else -1)
                fee = abs(exit_price * quantity) * self.config.fee_bps / 10000
                equity += pnl - fee
                trades.append(BacktestTrade(ordered[i].timestamp, exit_side, quantity, price, exit_price, fee, pnl - fee))
                position_side = None
                quantity = 0.0
            position_side = signal.action
            quantity = max(1.0, equity / price * 0.01)
            entry = self._fill_price(price, position_side)
            fee = abs(entry * quantity) * self.config.fee_bps / 10000
            equity -= fee
            trades.append(BacktestTrade(ordered[i].timestamp, position_side, quantity, price, entry, fee, -fee))
            curve.append(equity)

        if position_side is not None:
            last = ordered[-1]
            exit_side = "SELL" if position_side == "BUY" else "BUY"
            exit_price = self._fill_price(float(last.close), exit_side)
            pnl = (exit_price - entry) * quantity * (1 if position_side == "BUY" else -1)
            fee = abs(exit_price * quantity) * self.config.fee_bps / 10000
            equity += pnl - fee
            trades.append(BacktestTrade(last.timestamp, exit_side, quantity, float(last.close), exit_price, fee, pnl - fee))
            curve.append(equity)
        if not isfinite(equity) or any(not isfinite(float(value)) for value in curve):
            raise ValueError("backtest produced non-finite equity")
        return BacktestResult(self.config.initial_equity, equity, tuple(trades), tuple(curve))

    def _fill_price(self, price: float, side: str) -> float:
        if side not in {"BUY", "SELL"} or not isfinite(float(price)) or price <= 0:
            raise ValueError("invalid fill request")
        slip = self.config.slippage_bps / 10000
        fill = price * (1 + slip if side == "BUY" else 1 - slip)
        if not isfinite(fill) or fill <= 0:
            raise ValueError("invalid fill price")
        return fill
