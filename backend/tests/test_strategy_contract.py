from datetime import datetime, timedelta, timezone

import pytest

import backend.app.strategy as strategy
from backend.app.market_data import Candle


BASE = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)


def candles(count=20, symbol="NSE_TEST"):
    return [
        Candle(
            timestamp=BASE + timedelta(minutes=5 * i),
            symbol=symbol,
            timeframe="5m",
            open=100 + i * 0.1,
            high=101 + i * 0.1,
            low=99 + i * 0.1,
            close=100.5 + i * 0.1,
            volume=100,
        )
        for i in range(count)
    ]


def test_strategy_rejects_invalid_configuration():
    series = candles()
    with pytest.raises(ValueError):
        strategy.generate_signal(series, min_score=0)
    with pytest.raises(ValueError):
        strategy.generate_signal(series, min_score=True)
    with pytest.raises(ValueError):
        strategy.generate_signal(series, max_age_seconds=-1)
    with pytest.raises(ValueError):
        strategy.generate_signal(series, max_age_seconds=float("inf"))
    with pytest.raises(ValueError):
        strategy.generate_signal(series, require_mtf=1)


def test_strategy_rejects_invalid_market_data_and_mismatched_htf():
    series = candles()
    malformed = list(series)
    malformed[-1] = Candle(
        timestamp=malformed[-1].timestamp,
        symbol=malformed[-1].symbol,
        timeframe=malformed[-1].timeframe,
        open=100,
        high=101,
        low=99,
        close=float("nan"),
        volume=100,
    )
    assert strategy.generate_signal(malformed) is None
    assert strategy.generate_signal(series, htf_candles=candles(symbol="OTHER")) is None


def test_strategy_fails_closed_on_invalid_scoring_result(monkeypatch):
    series = candles()
    monkeypatch.setattr(strategy, "score", lambda _: {"score": float("nan"), "bias": "BULLISH", "reasons": []})
    assert strategy.generate_signal(series) is None

    monkeypatch.setattr(strategy, "score", lambda _: {"score": 3, "bias": "UNKNOWN", "reasons": []})
    assert strategy.generate_signal(series) is None


def test_strategy_generates_deterministic_candidate_without_execution(monkeypatch):
    series = candles()
    monkeypatch.setattr(
        strategy,
        "score",
        lambda _: {"score": 4, "bias": "BULLISH", "reasons": ["test confluence"], "atr": 2.0},
    )
    signal = strategy.generate_signal(series, min_score=2)
    assert signal is not None
    assert signal.action == "BUY"
    assert signal.entry == pytest.approx(series[-1].close)
    assert signal.stop_loss == pytest.approx(series[-1].close - 3.0)
    assert signal.target == pytest.approx(series[-1].close + 6.0)
    assert signal.risk_reward == pytest.approx(2.0)
    assert 0 < signal.confidence <= 0.99
    assert signal.reason == ["test confluence"]


def test_strategy_rejects_non_finite_atr(monkeypatch):
    series = candles()
    monkeypatch.setattr(
        strategy,
        "score",
        lambda _: {"score": 4, "bias": "BULLISH", "reasons": [], "atr": float("inf")},
    )
    assert strategy.generate_signal(series) is None
