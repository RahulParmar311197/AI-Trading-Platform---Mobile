from datetime import datetime, timedelta, timezone
import math

import pytest

from app.market_context import Candle, MarketContext
from app.market_context_builder import MarketContextBuilder


def test_market_context_builder_produces_valid_context():
    start = datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc)
    candles = []
    price = 100.0
    for i in range(80):
        open_price = price
        close = price + (0.15 if i % 3 else -0.05)
        high = max(open_price, close) + 0.4
        low = min(open_price, close) - 0.4
        candles.append(Candle(
            timestamp=start + timedelta(minutes=5 * i),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000 + i,
        ))
        price = close

    context = MarketContextBuilder().build("NIFTY", "5m", candles)
    assert context.symbol == "NIFTY"
    assert context.timeframe == "5m"
    assert len(context.candles) == 80
    assert context.indicators.values["ema_20"] is not None
    assert context.indicators.values["rsi_14"] is not None
    assert context.smc is not None
    assert context.ict is not None
    assert context.validate() is None


def test_market_context_builder_rejects_empty_candles():
    with pytest.raises(ValueError, match="at least one candle"):
        MarketContextBuilder().build("NIFTY", "5m", [])


def _valid_context(candle: Candle) -> MarketContext:
    return MarketContext(
        symbol="NIFTY",
        timeframe="5m",
        as_of=candle.timestamp,
        candles=(candle,),
    )


def test_market_context_rejects_non_finite_ohlcv():
    candle = Candle(
        timestamp=datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=math.nan,
    )
    with pytest.raises(ValueError, match="OHLCV must be finite"):
        _valid_context(candle).validate()


def test_market_context_rejects_naive_timestamps():
    candle = Candle(
        timestamp=datetime(2026, 8, 26, 9, 15),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        _valid_context(candle).validate()
