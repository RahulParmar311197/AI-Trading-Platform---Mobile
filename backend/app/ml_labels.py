from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class FutureReturnLabel:
    timestamp: object
    symbol: str
    horizon: int
    future_return: float
    label: str


def label_candle(candles: list[Candle], index: int, horizon: int = 5, threshold: float = 0.002) -> FutureReturnLabel | None:
    """Label a prediction bar only when the complete future window exists."""
    if horizon <= 0 or threshold < 0 or index < 0 or index >= len(candles):
        raise ValueError("invalid label parameters")
    if index + horizon >= len(candles):
        return None
    current = candles[index]
    future = candles[index + horizon]
    if current.close <= 0:
        raise ValueError("current close must be positive")
    future_return = future.close / current.close - 1.0
    if future_return >= threshold:
        label = "BUY"
    elif future_return <= -threshold:
        label = "SELL"
    else:
        label = "NEUTRAL"
    return FutureReturnLabel(current.timestamp, current.symbol, horizon, future_return, label)


def build_labels(candles: list[Candle], horizon: int = 5, threshold: float = 0.002) -> list[FutureReturnLabel]:
    data = sorted(candles, key=lambda c: c.timestamp)
    return [label_candle(data, i, horizon, threshold) for i in range(len(data) - horizon) if label_candle(data, i, horizon, threshold) is not None]
