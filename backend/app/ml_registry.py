from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json

@dataclass(frozen=True)
class ModelArtifact:
    model_name: str
    version: str
    feature_schema: tuple[str, ...]
    label_horizon: int
    label_threshold: float
    training_start: object
    training_end: object
    validation_accuracy: float
    baseline_accuracy: float
    artifact_sha256: str
    created_at: object

    @classmethod
    def create(cls, *, model_name: str, version: str, feature_schema: tuple[str, ...], label_horizon: int,
               label_threshold: float, training_start: object, training_end: object,
               validation_accuracy: float, baseline_accuracy: float, artifact_bytes: bytes) -> 'ModelArtifact':
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        return cls(model_name, version, feature_schema, label_horizon, label_threshold,
                   training_start, training_end, validation_accuracy, baseline_accuracy,
                   digest, datetime.now(timezone.utc))

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, sort_keys=True)


def validate_artifact(artifact: ModelArtifact, expected_features: tuple[str, ...],
                      expected_horizon: int, expected_threshold: float) -> None:
    if artifact.feature_schema != expected_features:
        raise ValueError('model feature schema mismatch')
    if artifact.label_horizon != expected_horizon:
        raise ValueError('model label horizon mismatch')
    if artifact.label_threshold != expected_threshold:
        raise ValueError('model label threshold mismatch')
    if artifact.validation_accuracy < artifact.baseline_accuracy:
        raise ValueError('model does not beat baseline')
