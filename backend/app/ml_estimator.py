from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from typing import Sequence
from app.ml_dataset import TrainingExample
from app.ml_features import FeatureVector

LABELS = ('BUY', 'SELL', 'NEUTRAL')

@dataclass(frozen=True)
class TrainableModel:
    """Dependency-free deterministic classifier contract.

    This baseline is intentionally simple; production estimators can implement
    the same fit/predict interface without changing inference or trading code.
    """
    class_centroids: dict[str, tuple[float, ...]]
    feature_names: tuple[str, ...]

    def predict(self, rows: Sequence[FeatureVector]) -> list[str]:
        return [self._nearest(row) for row in rows]

    def _nearest(self, row: FeatureVector) -> str:
        values = tuple(float(getattr(row, name)) for name in self.feature_names)
        if not self.class_centroids:
            raise ValueError('model has no trained classes')
        return min(self.class_centroids, key=lambda label: sum((a - b) ** 2 for a, b in zip(values, self.class_centroids[label])))


def fit_centroid_model(examples: Sequence[TrainingExample], feature_names: tuple[str, ...]) -> TrainableModel:
    if not examples:
        raise ValueError('training set cannot be empty')
    if not feature_names:
        raise ValueError('feature_names cannot be empty')
    grouped: dict[str, list[tuple[float, ...]]] = {}
    for example in examples:
        if example.label not in LABELS:
            raise ValueError(f'invalid label: {example.label}')
        grouped.setdefault(example.label, []).append(tuple(float(example.features[name]) for name in feature_names))
    centroids = {
        label: tuple(sum(row[i] for row in rows) / len(rows) for i in range(len(feature_names)))
        for label, rows in grouped.items()
    }
    return TrainableModel(centroids, feature_names)
