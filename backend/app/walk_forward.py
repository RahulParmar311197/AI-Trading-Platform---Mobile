from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[dict]
    aggregate: dict


def build_windows(length: int, train_size: int, test_size: int, step: int | None = None) -> list[WalkForwardWindow]:
    if length <= 0 or train_size <= 0 or test_size <= 0:
        raise ValueError("length and window sizes must be positive")
    step = step or test_size
    if step <= 0:
        raise ValueError("step must be positive")
    windows = []
    start = 0
    while start + train_size + test_size <= length:
        train_end = start + train_size
        windows.append(WalkForwardWindow(start, train_end, train_end, train_end + test_size))
        start += step
    return windows


def run_walk_forward(
    candles: list[Any],
    train_size: int,
    test_size: int,
    optimizer: Callable[[list[Any]], Any],
    evaluator: Callable[[list[Any], Any], dict],
    step: int | None = None,
) -> WalkForwardResult:
    """Run strictly sequential train-then-test windows with no future leakage."""
    windows = build_windows(len(candles), train_size, test_size, step)
    rows = []
    for w in windows:
        train = candles[w.train_start:w.train_end]
        test = candles[w.test_start:w.test_end]
        params = optimizer(train)
        metrics = evaluator(test, params)
        rows.append({
            "train_start": w.train_start,
            "train_end": w.train_end,
            "test_start": w.test_start,
            "test_end": w.test_end,
            "parameters": params,
            "metrics": metrics,
        })

    pnl = [float(r["metrics"].get("net_pnl", 0.0)) for r in rows]
    profitable = [p for p in pnl if p > 0]
    aggregate = {
        "windows": len(rows),
        "net_pnl": sum(pnl),
        "profitable_windows": len(profitable),
        "window_win_rate": len(profitable) / len(pnl) if pnl else 0.0,
        "leakage_policy": "train window ends before test window begins",
    }
    return WalkForwardResult(rows, aggregate)
