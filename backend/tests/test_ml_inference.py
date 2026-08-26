from datetime import datetime, timezone
import pytest

from app.ml_features import FeatureVector
from app.ml_inference import predict_one
from app.ml_registry import ModelArtifact


class StubModel:
    def __init__(self, label='BUY'):
        self.label = label
    def predict(self, rows):
        return [self.label]


def feature():
    return FeatureVector(datetime.now(timezone.utc), 'TEST', 0, 0, 0, 1, 1, 0, 0, 0, 0, 0)


def artifact(features):
    return ModelArtifact.create(
        model_name='baseline', version='1', feature_schema=features,
        label_horizon=5, label_threshold=0.002,
        training_start=feature().timestamp, training_end=feature().timestamp,
        validation_accuracy=.5, baseline_accuracy=.4, artifact_bytes=b'model')


def test_inference_accepts_matching_schema():
    schema = ('ema_distance', 'atr_normalized', 'volatility_normalized', 'structure_score', 'bullish', 'bearish', 'liquidity_sweep', 'fvg_state', 'order_block_state', 'premium_discount')
    result = predict_one(StubModel(), artifact(schema), feature(), schema, 5, .002)
    assert result.label == 'BUY'
    assert result.model_version == '1'


def test_inference_rejects_schema_mismatch():
    schema = ('ema_distance',)
    with pytest.raises(ValueError, match='feature schema mismatch'):
        predict_one(StubModel(), artifact(schema), feature(), ('atr_normalized',), 5, .002)


def test_inference_rejects_invalid_model_label():
    schema = ('ema_distance',)
    with pytest.raises(ValueError, match='invalid trading label'):
        predict_one(StubModel('HOLD'), artifact(schema), feature(), schema, 5, .002)
