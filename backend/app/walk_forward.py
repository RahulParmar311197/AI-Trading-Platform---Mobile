from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Callable, Sequence, Any

from app.market_context import Candle


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train: tuple[Any, ...]
    test: tuple[Any, ...]


@dataclass(frozen=True)
class WindowBounds:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WalkForwardResult:
    windows: tuple[dict[str, Any], ...]
    aggregate: dict[str, Any]


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


def build_windows(total: int, train_size: int, test_size: int, step: int | None = None) -> tuple[WindowBounds, ...]:
    """Build index-only rolling windows for deterministic walk-forward tests."""
    if total < 0:
        raise ValueError("total must be non-negative")
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")
    result: list[WindowBounds] = []
    start = 0
    index = 0
    while start + train_size + test_size <= total:
        train_end = start + train_size
        test_end = train_end + test_size
        result.append(WindowBounds(index, start, train_end, train_end, test_end))
        start += step
        index += 1
    return tuple(result)


def run_walk_forward(
    candles: Sequence[Any],
    train_size: int,
    test_size: int,
    train_fn: Callable[[Sequence[Any]], Any],
    test_fn: Callable[[Sequence[Any], Any], dict[str, Any]],
    step: int | None = None,
) -> WalkForwardResult:
    """Run chronological train/test evaluations and aggregate test metrics."""
    values = tuple(candles)
    bounds = build_windows(len(values), train_size, test_size, step)
    rows: list[dict[str, Any]] = []
    for bound in bounds:
        train = values[bound.train_start:bound.train_end]
        test = values[bound.test_start:bound.test_end]
        params = train_fn(train)
        metrics = dict(test_fn(test, params))
        rows.append({
            "index": bound.index,
            "train_start": bound.train_start,
            "train_end": bound.train_end,
            "test_start": bound.test_start,
            "test_end": bound.test_end,
            **metrics,
        })
    pnls = [float(row["net_pnl"]) for row in rows if "net_pnl" in row]
    aggregate: dict[str, Any] = {"windows": len(rows)}
    if pnls:
        aggregate.update({"net_pnl": sum(pnls), "mean_net_pnl": mean(pnls), "profitable_windows": sum(p > 0 for p in pnls)})
    return WalkForwardResult(windows=tuple(rows), aggregate=aggregate)
