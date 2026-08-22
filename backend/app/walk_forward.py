from __future__ import annotations

from app.ml_training import baseline_metrics, make_dataset
from app.market_data import Candle


def walk_forward(candles: list[Candle], train_size: int = 500, test_size: int = 100, step: int = 100, horizon: int = 5) -> dict:
    if train_size < 30 or test_size < 1 or step < 1:
        raise ValueError("invalid walk-forward parameters")
    windows = []
    start = 0
    while start + train_size + test_size <= len(candles):
        train = make_dataset(candles[start:start + train_size], horizon)
        test = make_dataset(candles[start + train_size:start + train_size + test_size], horizon)
        windows.append({"start": start, "train": baseline_metrics(train), "test": baseline_metrics(test)})
        start += step
    return {"windows": len(windows), "results": windows}
