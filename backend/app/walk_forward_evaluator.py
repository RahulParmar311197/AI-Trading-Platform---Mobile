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
        return sum(r.net_pnl for r in self.windows)

    @property
    def average_win_rate(self) -> float:
        return sum(r.win_rate for r in self.windows) / len(self.windows) if self.windows else 0.0

    @property
    def worst_drawdown(self) -> float:
        return max((r.max_drawdown for r in self.windows), default=0.0)

    @property
    def profitable_windows(self) -> int:
        return sum(r.net_pnl > 0 for r in self.windows)


class WalkForwardEvaluator:
    """Evaluate strategy performance only on unseen test windows."""

    def __init__(self, engine: BacktestEngine | None = None) -> None:
        self.engine = engine or BacktestEngine()

    def evaluate(self, candles: Sequence[Candle], *, train_size: int, test_size: int, signal_factory: Callable[[tuple[Candle, ...]], Callable[[int, Sequence[Candle]], tuple[str, int] | None]], step: int | None = None, warmup_size: int = 0) -> WalkForwardEvaluation:
        if warmup_size < 0:
            raise ValueError("warmup_size must be non-negative")
        values = tuple(candles)
        windows = make_walk_forward_windows(values, train_size=train_size, test_size=test_size, step=step)
        results: list[BacktestResult] = []
        for window in windows:
            test_start = values.index(window.test[0])
            warmup_start = max(0, test_start - warmup_size)
            analysis_candles = values[warmup_start:test_start] + window.test
            base_signal = signal_factory(window.train)

            def signal(index: int, visible: Sequence[Candle], *, _base=base_signal, _offset=len(values[warmup_start:test_start])):
                # Warm-up bars are analysis-only; no trade can be opened from them.
                if index < _offset:
                    return None
                return _base(index - _offset, visible[_offset:])

            results.append(self.engine.run(analysis_candles, signal))
        return WalkForwardEvaluation(tuple(results))
