from datetime import datetime, timedelta, timezone

from app.market_data import Candle
from app.ml_dataset import build_training_dataset


def candles(n=30):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="TEST",
            timestamp=start + timedelta(minutes=i),
            open=100 + i * 0.1,
            high=101 + i * 0.1,
            low=99 + i * 0.1,
            close=100 + i * 0.1,
            volume=1000,
        )
        for i in range(n)
    ]


def test_dataset_excludes_incomplete_future_window():
    data = candles(25)
    examples = build_training_dataset(data, horizon=5, threshold=0.001)
    assert len(examples) == 20
    assert examples[-1].timestamp == data[19].timestamp


def test_feature_timestamp_matches_label_timestamp():
    examples = build_training_dataset(candles(30), horizon=5, threshold=0.001)
    assert examples
    for example in examples:
        assert example.features["timestamp"] == example.timestamp


def test_labels_use_future_return_not_future_feature_values():
    data = candles(30)
    examples = build_training_dataset(data, horizon=5, threshold=0.001)
    assert examples
    assert all(example.horizon == 5 for example in examples)
    assert all(example.timestamp < data[-1].timestamp for example in examples)
