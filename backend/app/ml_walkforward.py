from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Callable
from app.ml_dataset import TrainingExample
from app.ml_baseline import BaselineModel, ClassificationMetrics, evaluate, train_baseline

@dataclass(frozen=True)
class WalkForwardFold:
    train_size: int
    validation_size: int
    metrics: ClassificationMetrics


def walk_forward_baseline(
    examples: Sequence[TrainingExample],
    folds: int = 3,
    min_train_size: int | None = None,
    trainer: Callable[[Sequence[TrainingExample]], BaselineModel] = train_baseline,
) -> list[WalkForwardFold]:
    data = sorted(examples, key=lambda x: x.timestamp)
    if folds <= 0:
        raise ValueError('folds must be positive')
    if len(data) < folds + 1:
        raise ValueError('not enough examples for walk-forward evaluation')
    minimum = min_train_size if min_train_size is not None else max(1, len(data) // (folds + 1))
    if minimum <= 0:
        raise ValueError('min_train_size must be positive')
    available = len(data) - minimum
    if available < folds:
        raise ValueError('not enough examples after minimum training window')
    step = max(1, available // folds)
    results: list[WalkForwardFold] = []
    for fold in range(folds):
        train_end = minimum + step * fold
        validation_end = minimum + step * (fold + 1)
        if fold == folds - 1:
            validation_end = len(data)
        train = data[:train_end]
        validation = data[train_end:validation_end]
        if not validation:
            continue
        model = trainer(train)
        results.append(WalkForwardFold(len(train), len(validation), evaluate(model, validation)))
    if not results:
        raise ValueError('no walk-forward folds produced')
    return results
