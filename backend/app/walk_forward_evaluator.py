from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.backtest_engine import BacktestEngine, BacktestResult
from app.market_context import Candle
from app.walk_forward import make_walk_forward_windows


@dataclass(frozen=True)
class WalkForwardEvaluation:
    windows: tuple[BacktestResult, ...]

    @property
    def total_net_pnl(self) -> float:
        return sum(result.net_pnl for result in self.windows)

    @property
    def average_win_rate(self) -> float:
        return sum(result.win_rate for result in self.windows) / len(self.windows) if self.windows else 0.0

    @property
    def worst_drawdown(self) -> float:
        return max((result.max_drawdown for result in self.windows), default=0.0)

    @property
    def profitable_windows(self) -> int:
        return sum(result.net_pnl > 0 for result in self.windows)


class WalkForwardEvaluator:
    def __init__(self, engine: BacktestEngine | None = None) -> None:
        self.engine = engine or BacktestEngine()

    def evaluate(self, candles: Sequence[Candle], *, train_size: int, test_size: int, signal_factory: Callable[[tuple[Candle, ...]], Callable[[int, Sequence[Candle]], tuple[str, int] | None]], step: int | None = None) -> WalkForwardEvaluation:
        windows = make_walk_forward_windows(candles, train_size=train_size, test_size=test_size, step=step)
        results = []
        for window in windows:
            signal = signal_factory(window.train)
            results.append(self.engine.run(window.test, signal))
        return WalkForwardEvaluation(tuple(results))
