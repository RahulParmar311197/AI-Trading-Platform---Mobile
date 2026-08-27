from datetime import datetime, timedelta, timezone

import pytest

from app.ai_decision_engine import AIDecisionEngine
from app.market_context import Candle, IndicatorSnapshot, MarketContext, StructureSnapshot


def context(*, quality="GOOD", indicators=None):
    start = datetime(2026, 8, 27, 9, tzinfo=timezone.utc)
    candles = tuple(
        Candle(start + timedelta(minutes=15 * i), 100 + i, 102 + i, 99 + i, 101 + i, 1000)
        for i in range(60)
    )
    return MarketContext(
        symbol="NIFTY",
        timeframe="15m",
        as_of=candles[-1].timestamp,
        candles=candles,
        indicators=IndicatorSnapshot(indicators or {}),
        structure=StructureSnapshot(trend="BULLISH", bos="BULLISH"),
        data_quality=quality,
    )


def complete_indicators(atr=1.0):
    return {
        "ema_20": 105.0,
        "ema_50": 100.0,
        "rsi_14": 60.0,
        "macd_histogram": 1.0,
        "atr_14": atr,
    }


def test_missing_trade_indicator_forces_hold():
    d = AIDecisionEngine().decide(context(indicators={"ema_20": 105.0, "ema_50": 100.0}))
    assert d.decision == "HOLD"
    assert d.entry is None
    assert any("missing required indicators" in reason for reason in d.reasons)


def test_unknown_data_quality_cannot_generate_trade():
    d = AIDecisionEngine().decide(context(quality="UNKNOWN", indicators=complete_indicators()))
    assert d.decision == "HOLD"
    assert d.entry is None
    assert any("data quality not trade-ready" in reason for reason in d.reasons)


def test_non_positive_atr_cannot_generate_trade():
    d = AIDecisionEngine().decide(context(indicators=complete_indicators(atr=0.0)))
    assert d.decision == "HOLD"
    assert d.entry is None
    assert any("ATR must be positive" in reason for reason in d.reasons)


def test_complete_trade_inputs_produce_bounded_risk_levels():
    d = AIDecisionEngine().decide(context(indicators=complete_indicators()))
    assert d.decision == "BUY"
    assert d.entry is not None
    assert d.stop_loss is not None and d.stop_loss < d.entry
    assert d.target is not None and d.target > d.entry


def test_invalid_ml_confidence_is_rejected():
    with pytest.raises(ValueError, match="ml_confidence"):
        AIDecisionEngine().decide(context(indicators=complete_indicators()), ml_confidence=1.1)
