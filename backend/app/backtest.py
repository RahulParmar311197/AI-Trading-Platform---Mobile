from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.accounting import EquitySnapshot, calculate_equity
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
    gross_pnl: float = 0.0


@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    final_equity: float
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[float, ...]

    @property
    def net_pnl(self) -> float:
        return self.final_equity - self.initial_equity

    @property
    def gross_pnl(self) -> float:
        return sum(t.gross_pnl for t in self.trades)

    @property
    def fees(self) -> float:
        return sum(t.fees for t in self.trades)


class _BacktestPosition:
    def __init__(self) -> None:
        self.side: str | None = None
        self.quantity = 0.0
        self.entry_price = 0.0

    def close(self, price: float) -> float:
        if self.side is None or self.quantity <= 0:
            return 0.0
        gross = (price - self.entry_price) * self.quantity * (1 if self.side == 'BUY' else -1)
        self.side = None
        self.quantity = 0.0
        self.entry_price = 0.0
        return gross

    def open(self, side: str, price: float, quantity: float) -> None:
        self.side = side
        self.quantity = quantity
        self.entry_price = price

    def mark_to_market(self, price: float) -> float:
        if self.side is None or self.quantity <= 0:
            return 0.0
        return (price - self.entry_price) * self.quantity * (1 if self.side == 'BUY' else -1)


class CandleBacktester:
    """Deterministic strategy replay; never calls live broker/execution services."""
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        if self.config.initial_equity <= 0:
            raise ValueError('initial_equity must be positive')
        if self.config.fee_bps < 0 or self.config.slippage_bps < 0:
            raise ValueError('fee_bps and slippage_bps must be non-negative')

    def _fee(self, price: float, quantity: float) -> float:
        return abs(price * quantity) * self.config.fee_bps / 10000

    def run(self, candles: list[Candle]) -> BacktestResult:
        if not candles:
            initial = self.config.initial_equity
            return BacktestResult(initial, initial, (), (initial,))

        ordered = sorted(candles, key=lambda c: c.timestamp)
        realized = 0.0
        fees = 0.0
        position = _BacktestPosition()
        trades: list[BacktestTrade] = []
        curve = [self.config.initial_equity]

        for i in range(20, len(ordered)):
            candle = ordered[i]
            signal: TradeSignal | None = generate_signal(
                ordered[: i + 1],
                min_score=self.config.signal_min_score,
                max_age_seconds=self.config.freshness_seconds,
                now=candle.timestamp,
            )
            if signal is not None and position.side != signal.action:
                action = signal.action
                price = signal.entry
                if position.side is not None:
                    exit_side = 'SELL' if position.side == 'BUY' else 'BUY'
                    exit_price = self._fill_price(price, exit_side)
                    quantity = position.quantity
                    gross = position.close(exit_price)
                    fee = self._fee(exit_price, quantity)
                    realized += gross
                    fees += fee
                    trades.append(BacktestTrade(candle.timestamp, exit_side, quantity, price, exit_price, fee, gross - fee, gross))

                quantity = max(1.0, self.config.initial_equity / max(price, 1e-12) * 0.01)
                entry_price = self._fill_price(price, action)
                fee = self._fee(entry_price, quantity)
                fees += fee
                position.open(action, entry_price, quantity)
                trades.append(BacktestTrade(candle.timestamp, action, quantity, price, entry_price, fee, -fee, 0.0))

            mark_price = self._fill_price(candle.close, 'SELL' if position.side == 'BUY' else 'BUY') if position.side else candle.close
            unrealized = position.mark_to_market(mark_price)
            snapshot = EquitySnapshot(
                starting_equity=self.config.initial_equity,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                fees=fees,
                charges=0.0,
            )
            curve.append(calculate_equity(snapshot))

        if position.side is not None:
            last = ordered[-1]
            exit_side = 'SELL' if position.side == 'BUY' else 'BUY'
            exit_price = self._fill_price(last.close, exit_side)
            quantity = position.quantity
            gross = position.close(exit_price)
            fee = self._fee(exit_price, quantity)
            realized += gross
            fees += fee
            trades.append(BacktestTrade(last.timestamp, exit_side, quantity, last.close, exit_price, fee, gross - fee, gross))

        final_snapshot = EquitySnapshot(
            starting_equity=self.config.initial_equity,
            realized_pnl=realized,
            unrealized_pnl=0.0,
            fees=fees,
            charges=0.0,
        )
        final_equity = calculate_equity(final_snapshot)
        curve[-1] = final_equity
        return BacktestResult(self.config.initial_equity, final_equity, tuple(trades), tuple(curve))

    def _fill_price(self, price: float, side: str) -> float:
        slip = self.config.slippage_bps / 10000
        return price * (1 + slip if side == 'BUY' else 1 - slip)
