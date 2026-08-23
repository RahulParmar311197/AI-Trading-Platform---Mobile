from datetime import datetime, timedelta, timezone

from app.market_data import Candle
from app.scanner import MarketScanner


def test_scanner_requires_enough_candles():
    candles = [Candle(datetime.now(timezone.utc), 100, 101, 99, 100, 1, "NIFTY", "5m") for _ in range(29)]
    try:
        MarketScanner().scan(candles)
    except ValueError as exc:
        assert "30" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_scanner_normalizes_symbol_and_returns_signal(monkeypatch):
    class Decision:
        action = "BUY"
        score = 0.8
        confidence = 0.8
        ai_probability_up = 0.9
        technical_score = 2.0
        regime = "NORMAL"
        reasons = ["test"]

    monkeypatch.setattr("app.scanner.decide", lambda candles: Decision())
    base = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
    candles = [Candle(base + timedelta(minutes=i), 100, 102, 99, 101, 1000, " nifty ", "5m") for i in range(30)]
    signal = MarketScanner().scan(candles)
    assert signal.symbol == "NIFTY"
    assert signal.action == "BUY"
    assert signal.confidence == 0.8


def test_scanner_suppresses_low_confidence(monkeypatch):
    class Decision:
        action = "SELL"
        score = -0.4
        confidence = 0.2
        ai_probability_up = 0.3
        technical_score = -1.0
        regime = "NORMAL"
        reasons = []

    monkeypatch.setattr("app.scanner.decide", lambda candles: Decision())
    base = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
    candles = [Candle(base + timedelta(minutes=i), 100, 102, 99, 101, 1000, "NIFTY", "5m") for i in range(30)]
    signal = MarketScanner().scan(candles, min_confidence=0.35)
    assert signal.action == "NO_TRADE"
