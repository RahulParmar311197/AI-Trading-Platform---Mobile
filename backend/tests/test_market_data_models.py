from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.market_data import Candle, Instrument, Tick, Timeframe


def instrument():
    return Instrument(symbol=" reliance ", exchange=" nse ")


def test_instrument_identifiers_are_normalized():
    value = instrument()
    assert value.symbol == "RELIANCE"
    assert value.exchange == "NSE"


def test_candle_accepts_valid_ohlcv():
    value = Candle(
        instrument=instrument(),
        timeframe=Timeframe.FIVE_MINUTES,
        timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
        open=100,
        high=105,
        low=98,
        close=103,
        volume=1000,
    )
    assert value.timestamp.tzinfo is not None
    assert value.high == 105


def test_candle_rejects_invalid_ohlc_range():
    with pytest.raises(ValidationError):
        Candle(
            instrument=instrument(),
            timeframe=Timeframe.FIVE_MINUTES,
            timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
            open=100,
            high=99,
            low=98,
            close=103,
        )


def test_candle_rejects_naive_timestamp():
    with pytest.raises(ValidationError):
        Candle(
            instrument=instrument(),
            timeframe=Timeframe.FIVE_MINUTES,
            timestamp=datetime(2026, 8, 31, 9, 15),
            open=100,
            high=105,
            low=98,
            close=103,
        )


def test_tick_rejects_non_positive_price_and_negative_volume():
    with pytest.raises(ValidationError):
        Tick(
            instrument=instrument(),
            timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
            price=0,
            volume=0,
        )
    with pytest.raises(ValidationError):
        Tick(
            instrument=instrument(),
            timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
            price=100,
            volume=-1,
        )


def test_models_are_immutable():
    value = instrument()
    with pytest.raises(ValidationError):
        value.symbol = "INFY"
