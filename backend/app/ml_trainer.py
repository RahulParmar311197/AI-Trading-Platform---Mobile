from __future__ import annotations

from dataclasses import dataclass
from app.ml_metrics import classification_metrics


@dataclass
class ThresholdModel:
    threshold: float = 0.0

    def fit(self, examples: list[dict]):
        if not examples: raise ValueError("no training examples")
        self.threshold = sum(x["ema_spread_pct"] for x in examples) / len(examples)
        return self

    def predict_proba(self, examples: list[dict]) -> list[float]:
        if not examples: return []
        spread_scale = max(0.01, max(abs(x["ema_spread_pct"] - self.threshold) for x in examples))
        return [min(0.99, max(0.01, 0.5 + 0.45 * (x["ema_spread_pct"] - self.threshold) / spread_scale)) for x in examples]


def train(examples: list, validation: list) -> dict:
    model = ThresholdModel().fit([x.features for x in examples])
    labels = [x.label for x in validation]
    probabilities = model.predict_proba([x.features for x in validation])
    metrics = classification_metrics(labels, probabilities)
    return {"model": model, "metrics": metrics}
