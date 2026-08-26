from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence

from app.ml_features import FeatureVector
from app.ml_registry import ModelArtifact, validate_artifact


class Predictor(Protocol):
    def predict(self, rows: Sequence[FeatureVector]) -> list[str]: ...


@dataclass(frozen=True)
class Prediction:
    symbol: str
    timestamp: object
    label: str
    model_name: str
    model_version: str


def predict_one(
    model: Predictor,
    artifact: ModelArtifact,
    features: FeatureVector,
    expected_features: tuple[str, ...],
    expected_horizon: int,
    expected_threshold: float,
) -> Prediction:
    validate_artifact(artifact, expected_features, expected_horizon, expected_threshold)
    values = tuple(getattr(features, name) for name in expected_features)
    if len(values) != len(expected_features):
        raise ValueError("feature vector schema mismatch")
    label = model.predict([features])[0]
    if label not in {"BUY", "SELL", "NEUTRAL"}:
        raise ValueError("model returned invalid trading label")
    return Prediction(features.symbol, features.timestamp, label, artifact.model_name, artifact.version)
