from datetime import datetime, timedelta, timezone

from app.market_context import Candle
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
            symbol="NIFTY",
            timeframe="5m",
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
    assert context.validate() is True


def test_market_context_builder_rejects_empty_candles():
    import pytest

    with pytest.raises(ValueError, match="at least one candle"):
        MarketContextBuilder().build("NIFTY", "5m", [])
