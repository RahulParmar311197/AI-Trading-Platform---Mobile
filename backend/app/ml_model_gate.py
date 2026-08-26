from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from typing import Sequence
from app.ml_dataset import TrainingExample
from app.ml_walkforward import WalkForwardFold

@dataclass(frozen=True)
class ModelGateConfig:
    min_samples: int = 100
    min_class_fraction: float = 0.05
    min_mean_accuracy: float = 0.34
    min_baseline_lift: float = 0.0

@dataclass(frozen=True)
class ModelGateResult:
    approved: bool
    reasons: tuple[str, ...]
    mean_accuracy: float
    baseline_accuracy: float


def evaluate_model_gate(
    examples: Sequence[TrainingExample],
    folds: Sequence[WalkForwardFold],
    baseline_folds: Sequence[WalkForwardFold],
    config: ModelGateConfig | None = None,
) -> ModelGateResult:
    cfg = config or ModelGateConfig()
    reasons: list[str] = []
    if len(examples) < cfg.min_samples:
        reasons.append('insufficient_samples')
    counts = Counter(x.label for x in examples)
    total = len(examples)
    if total:
        for label in ('BUY', 'SELL', 'NEUTRAL'):
            if counts.get(label, 0) / total < cfg.min_class_fraction:
                reasons.append(f'class_underrepresented:{label}')
    if not folds or not baseline_folds:
        reasons.append('missing_walk_forward_results')
        mean_accuracy = 0.0
        baseline_accuracy = 0.0
    else:
        mean_accuracy = sum(f.metrics.accuracy for f in folds) / len(folds)
        baseline_accuracy = sum(f.metrics.accuracy for f in baseline_folds) / len(baseline_folds)
        if mean_accuracy < cfg.min_mean_accuracy:
            reasons.append('accuracy_below_threshold')
        if mean_accuracy < baseline_accuracy + cfg.min_baseline_lift:
            reasons.append('does_not_beat_baseline')
    return ModelGateResult(not reasons, tuple(reasons), mean_accuracy, baseline_accuracy)
