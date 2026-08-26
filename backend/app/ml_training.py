from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.ml_dataset import TrainingExample
from app.ml_estimator import TrainableModel, fit_centroid_model
from app.ml_baseline import ClassificationMetrics
from app.ml_walkforward import WalkForwardFold, walk_forward_baseline
from app.ml_model_gate import ModelGateConfig, ModelGateResult, evaluate_model_gate
from app.ml_features import FeatureVector


@dataclass(frozen=True)
class TrainingRun:
    model: TrainableModel
    folds: tuple[WalkForwardFold, ...]
    baseline_folds: tuple[WalkForwardFold, ...]
    gate: ModelGateResult


def _to_features(example: TrainingExample) -> FeatureVector:
    values = dict(example.features)
    return FeatureVector(
        timestamp=values['timestamp'],
        symbol=values['symbol'],
        ema_distance=float(values['ema_distance']),
        atr_normalized=float(values['atr_normalized']),
        volatility_normalized=float(values['volatility_normalized']),
        structure_score=float(values['structure_score']),
        bullish=int(values['bullish']),
        bearish=int(values['bearish']),
        liquidity_sweep=int(values['liquidity_sweep']),
        fvg_state=int(values['fvg_state']),
        order_block_state=int(values['order_block_state']),
        premium_discount=int(values['premium_discount']),
    )


def train_and_gate(
    examples: Sequence[TrainingExample],
    feature_names: tuple[str, ...],
    *,
    folds: int = 3,
    min_train_size: int | None = None,
    config: ModelGateConfig | None = None,
) -> TrainingRun:
    data = sorted(examples, key=lambda x: x.timestamp)
    if not data:
        raise ValueError('training examples cannot be empty')
    if not feature_names:
        raise ValueError('feature_names cannot be empty')
    if folds <= 0:
        raise ValueError('folds must be positive')

    minimum = min_train_size if min_train_size is not None else max(1, len(data) // (folds + 1))
    available = len(data) - minimum
    if available < folds:
        raise ValueError('not enough examples for walk-forward training')
    step = max(1, available // folds)

    candidate_folds: list[WalkForwardFold] = []
    for fold in range(folds):
        train_end = minimum + step * fold
        validation_end = len(data) if fold == folds - 1 else minimum + step * (fold + 1)
        validation = data[train_end:validation_end]
        if not validation:
            continue
        model = fit_centroid_model(data[:train_end], feature_names)
        predictions = model.predict([_to_features(x) for x in validation])
        correct = sum(prediction == example.label for prediction, example in zip(predictions, validation))
        candidate_folds.append(
            WalkForwardFold(
                train_end,
                len(validation),
                ClassificationMetrics(correct / len(validation), len(validation), correct),
            )
        )

    baseline_folds = walk_forward_baseline(data, folds=folds, min_train_size=min_train_size)
    gate = evaluate_model_gate(data, candidate_folds, baseline_folds, config)
    final_model = fit_centroid_model(data, feature_names)
    return TrainingRun(final_model, tuple(candidate_folds), tuple(baseline_folds), gate)
