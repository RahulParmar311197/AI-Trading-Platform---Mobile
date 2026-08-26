from __future__ import annotations
from dataclasses import dataclass, asdict
from app.market_data import Candle
from app.ml_features import build_feature_vector
from app.ml_labels import label_candle

@dataclass(frozen=True)
class TrainingExample:
    symbol: str
    timestamp: object
    features: dict
    label: str
    future_return: float
    horizon: int


def build_training_dataset(candles: list[Candle], horizon: int = 5, threshold: float = 0.002) -> list[TrainingExample]:
    data = sorted(candles, key=lambda c: c.timestamp)
    examples: list[TrainingExample] = []
    for index in range(len(data) - horizon):
        label = label_candle(data, index, horizon, threshold)
        if label is None:
            continue
        # Features end at the same prediction bar; label only looks forward.
        features = build_feature_vector(data[: index + 1])
        if features is None or features.timestamp != label.timestamp:
            continue
        examples.append(TrainingExample(
            symbol=label.symbol,
            timestamp=label.timestamp,
            features=asdict(features),
            label=label.label,
            future_return=label.future_return,
            horizon=label.horizon,
        ))
    return examples
