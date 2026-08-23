from __future__ import annotations

from dataclasses import dataclass
from app.ai_features import build_features
from app.market_data import Candle


@dataclass(frozen=True)
class TrainingExample:
    features: dict
    label: int


def make_dataset(candles: list[Candle], horizon: int = 5, threshold: float = 0.0) -> list[TrainingExample]:
    if horizon < 1:
        raise ValueError("horizon must be positive")
    examples: list[TrainingExample] = []
    for end in range(30, len(candles) - horizon):
        window = candles[:end]
        features = build_features(window)
        future_return = candles[end + horizon - 1].close / candles[end - 1].close - 1
        label = 1 if future_return > threshold else 0
        examples.append(TrainingExample(features, label))
    return examples


def chronological_split(examples: list[TrainingExample], train_ratio: float = 0.7, validation_ratio: float = 0.15):
    if not 0 < train_ratio < 1 or not 0 < validation_ratio < 1 or train_ratio + validation_ratio >= 1:
        raise ValueError("invalid split ratios")
    n = len(examples)
    train_end = int(n * train_ratio)
    validation_end = train_end + int(n * validation_ratio)
    return examples[:train_end], examples[train_end:validation_end], examples[validation_end:]


def baseline_metrics(examples: list[TrainingExample]) -> dict:
    if not examples:
        return {"samples": 0, "accuracy": 0.0, "positive_rate": 0.0}
    predictions = [1 if x.features["ema_spread_pct"] > 0 else 0 for x in examples]
    correct = sum(p == x.label for p, x in zip(predictions, examples))
    positives = sum(x.label for x in examples)
    return {"samples": len(examples), "accuracy": correct / len(examples), "positive_rate": positives / len(examples)}
