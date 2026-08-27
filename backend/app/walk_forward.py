from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.market_context import Candle


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train: tuple[Candle, ...]
    test: tuple[Candle, ...]


def make_walk_forward_windows(candles: Sequence[Candle], *, train_size: int, test_size: int, step: int | None = None) -> tuple[WalkForwardWindow, ...]:
    """Create chronological train/test windows without future-data leakage."""
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")
    values = tuple(candles)
    windows: list[WalkForwardWindow] = []
    start = 0
    index = 0
    while start + train_size + test_size <= len(values):
        train_end = start + train_size
        test_end = train_end + test_size
        windows.append(WalkForwardWindow(index, values[start:train_end], values[train_end:test_end]))
        start += step
        index += 1
    return tuple(windows)
