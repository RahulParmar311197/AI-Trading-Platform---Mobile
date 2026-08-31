from datetime import datetime, timezone

import pytest

from app.market_data import Instrument, Tick, Timeframe
from app.market_data.aggregator import CandleAggregator


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")


def tick(second: int, price: float, volume: float = 1) -> Tick:
    return Tick(
        instrument=INSTRUMENT,
        timestamp=datetime(2026, 8, 31, 9, 15, second, tzinfo=timezone.utc),
        price=price,
        volume=volume,
    )


def test_aggregates_ohlcv_within_bucket():
    aggregator = CandleAggregator(Timeframe.ONE_MINUTE)
    assert aggregator.update(tick(5, 100, 10)) is None
    assert aggregator.update(tick(20, 105, 5)) is None
    assert aggregator.update(tick(50, 98, 7)) is None

    candle = aggregator.flush()
    assert candle is not None
    assert candle.timestamp == datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)
    assert candle.open == 100
    assert candle.high == 105
    assert candle.low == 98
    assert candle.close == 98
    assert candle.volume == 22


def test_next_bucket_emits_completed_candle():
    aggregator = CandleAggregator(Timeframe.ONE_MINUTE)
    aggregator.update(tick(10, 100))
    completed = aggregator.update(Tick(
        instrument=INSTRUMENT,
        timestamp=datetime(2026, 8, 31, 9, 16, 1, tzinfo=timezone.utc),
        price=102,
        volume=2,
    ))

    assert completed is not None
    assert completed.timestamp == datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)
    assert completed.close == 100
    assert aggregator.current.timestamp == datetime(2026, 8, 31, 9, 16, tzinfo=timezone.utc)


def test_late_tick_for_closed_bucket_is_rejected():
    aggregator = CandleAggregator(Timeframe.ONE_MINUTE)
    aggregator.update(tick(10, 100))
    aggregator.update(Tick(
        instrument=INSTRUMENT,
        timestamp=datetime(2026, 8, 31, 9, 16, tzinfo=timezone.utc),
        price=102,
    ))

    with pytest.raises(ValueError, match="closed candle"):
        aggregator.update(tick(20, 101))


def test_cross_instrument_tick_is_rejected():
    aggregator = CandleAggregator(Timeframe.ONE_MINUTE)
    aggregator.update(tick(10, 100))
    with pytest.raises(ValueError, match="instrument"):
        aggregator.update(Tick(
            instrument=Instrument(symbol="INFY", exchange="NSE"),
            timestamp=datetime(2026, 8, 31, 9, 15, 20, tzinfo=timezone.utc),
            price=1500,
        ))


def test_gap_does_not_create_fake_zero_volume_candles():
    aggregator = CandleAggregator(Timeframe.ONE_MINUTE)
    aggregator.update(tick(10, 100))
    completed = aggregator.update(Tick(
        instrument=INSTRUMENT,
        timestamp=datetime(2026, 8, 31, 9, 18, tzinfo=timezone.utc),
        price=103,
    ))

    assert completed is not None
    assert completed.timestamp.minute == 15
    assert aggregator.current.timestamp.minute == 18
