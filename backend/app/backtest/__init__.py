from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.backtest_engine import run_backtest
from app.market_data import Candle


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 100_000.0
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    signal_min_score: float = 0.0


@dataclass(frozen=True)
class BacktestTrade:
    timestamp: object
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float


@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    final_equity: float
    trades: tuple
    equity_curve: tuple[float, ...]


class CandleBacktester:
    """Compatibility facade over the canonical backtest engine."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        if self.config.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.config.fee_bps < 0 or self.config.slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")

    def run(self, candles: Sequence[Candle]) -> BacktestResult:
        result = run_backtest(
            list(candles),
            starting_equity=self.config.initial_equity,
            fee_bps=self.config.fee_bps,
            slippage_bps=self.config.slippage_bps,
        ) if candles else {
            "starting_equity": self.config.initial_equity,
            "ending_equity": self.config.initial_equity,
            "trade_journal": [],
            "equity_curve": [self.config.initial_equity],
        }
        trades = tuple(result.get("trade_journal", ()))
        return BacktestResult(
            initial_equity=float(result["starting_equity"]),
            final_equity=float(result["ending_equity"]),
            trades=trades,
            equity_curve=tuple(result["equity_curve"]),
        )


__all__ = ["BacktestConfig", "BacktestResult", "BacktestTrade", "CandleBacktester"]
