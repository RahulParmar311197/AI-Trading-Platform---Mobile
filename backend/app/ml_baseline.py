from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from typing import Sequence

from app.ml_dataset import TrainingExample

FEATURE_NAMES = (
    'ema_distance', 'atr_normalized', 'volatility_normalized', 'structure_score',
    'bullish', 'bearish', 'liquidity_sweep', 'fvg_state', 'order_block_state', 'premium_discount'
)

@dataclass(frozen=True)
class ChronologicalSplit:
    train: list[TrainingExample]
    validation: list[TrainingExample]

@dataclass(frozen=True)
class BaselineModel:
    class_probabilities: dict[str, float]
    majority_label: str

    def predict(self, examples: Sequence[TrainingExample]) -> list[str]:
        return [self.majority_label for _ in examples]

@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    samples: int
    correct: int


def chronological_split(examples: Sequence[TrainingExample], validation_fraction: float = 0.2) -> ChronologicalSplit:
    if not 0 < validation_fraction < 1:
        raise ValueError('validation_fraction must be between 0 and 1')
    data = sorted(examples, key=lambda x: x.timestamp)
    cut = int(len(data) * (1.0 - validation_fraction))
    if cut <= 0 or cut >= len(data):
        raise ValueError('not enough examples for chronological split')
    return ChronologicalSplit(data[:cut], data[cut:])


def train_baseline(train: Sequence[TrainingExample]) -> BaselineModel:
    if not train:
        raise ValueError('training set cannot be empty')
    counts = Counter(x.label for x in train)
    total = sum(counts.values())
    majority = max(counts, key=lambda label: (counts[label], label))
    return BaselineModel({label: count / total for label, count in counts.items()}, majority)


def evaluate(model: BaselineModel, validation: Sequence[TrainingExample]) -> ClassificationMetrics:
    if not validation:
        raise ValueError('validation set cannot be empty')
    predictions = model.predict(validation)
    correct = sum(pred == actual.label for pred, actual in zip(predictions, validation))
    return ClassificationMetrics(correct / len(validation), len(validation), correct)
