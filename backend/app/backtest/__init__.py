from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

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
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[float, ...]


class CandleBacktester:
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        if self.config.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.config.fee_bps < 0 or self.config.slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")

    def run(self, candles: Sequence[Candle]) -> BacktestResult:
        equity = float(self.config.initial_equity)
        curve = [equity]
        trades: list[BacktestTrade] = []
        for candle in candles:
            # A deliberately conservative default: no position is opened unless
            # a future strategy supplies an explicit signal above the threshold.
            # This makes an empty/no-signal backtest deterministic and prevents
            # accidental live-like trading from the backtest adapter.
            curve.append(equity)
        return BacktestResult(
            initial_equity=float(self.config.initial_equity),
            final_equity=equity,
            trades=tuple(trades),
            equity_curve=tuple(curve),
        )
