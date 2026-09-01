from datetime import datetime, timedelta, timezone
import pytest
from app.market_data import Candle, MarketTick, InMemoryMarketData, TickCandleAggregator, timeframe_seconds


def candle(ts, close=101):
    return Candle(ts,'NIFTY','5m',100,102,99,close,1000)


def test_candles_reject_out_of_order():
    data=InMemoryMarketData(); t=datetime.now(timezone.utc)
    assert data.put(candle(t))
    assert not data.put(candle(t-timedelta(minutes=5)))


def test_invalid_ohlc_rejected():
    data=InMemoryMarketData(); t=datetime.now(timezone.utc)
    with pytest.raises(ValueError): data.put(Candle(t,'NIFTY','5m',100,98,99,101,1))


def test_ticks_reject_duplicates_and_out_of_order():
    data=InMemoryMarketData(); t=datetime.now(timezone.utc)
    assert data.ingest_tick(MarketTick('NIFTY',t,100))
    assert not data.ingest_tick(MarketTick('NIFTY',t,101))
    assert not data.ingest_tick(MarketTick('NIFTY',t-timedelta(seconds=1),99))


def broker_row(ts, close=101):
    return {
        "timestamp": ts.isoformat(),
        "open": 100,
        "high": 102,
        "low": 99,
        "close": close,
        "volume": 1000,
    }


def test_broker_candle_batch_ingestion_is_atomic_on_malformed_row():
    data = InMemoryMarketData()
    now = datetime.now(timezone.utc)
    rows = [broker_row(now - timedelta(minutes=10)), {"timestamp": "not-a-timestamp"}]

    with pytest.raises(ValueError, match="invalid broker candle timestamp"):
        data.ingest_broker_candles("NIFTY", "5m", rows)

    assert data.candles("NIFTY", "5m") == []


def test_broker_candle_batch_rejects_invalid_ohlc_without_partial_write():
    data = InMemoryMarketData()
    now = datetime.now(timezone.utc)
    rows = [
        broker_row(now - timedelta(minutes=10)),
        {
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "open": 100,
            "high": 98,
            "low": 99,
            "close": 101,
            "volume": 1000,
        },
    ]

    with pytest.raises(ValueError, match="failed canonical validation"):
        data.ingest_broker_candles("NIFTY", "5m", rows)

    assert data.candles("NIFTY", "5m") == []


def test_broker_candle_batch_accepts_valid_rows_and_orders_them():
    data = InMemoryMarketData()
    now = datetime.now(timezone.utc)
    rows = [broker_row(now - timedelta(minutes=5), 102), broker_row(now - timedelta(minutes=10), 101)]

    assert data.ingest_broker_candles("NIFTY", "5m", rows) == 2
    candles = data.candles("NIFTY", "5m")
    assert len(candles) == 2
    assert candles[0].timestamp < candles[1].timestamp


def test_broker_candle_batch_rejects_future_row_without_partial_write():
    data = InMemoryMarketData()
    now = datetime.now(timezone.utc)
    rows = [broker_row(now - timedelta(minutes=5)), broker_row(now + timedelta(minutes=5))]

    with pytest.raises(ValueError, match="failed canonical validation"):
        data.ingest_broker_candles("NIFTY", "5m", rows)

    assert data.candles("NIFTY", "5m") == []


def test_timeframe_seconds_validates_fixed_utc_buckets():
    assert timeframe_seconds("1m") == 60
    assert timeframe_seconds("5m") == 300
    assert timeframe_seconds("1h") == 3600
    with pytest.raises(ValueError):
        timeframe_seconds("7m")
    with pytest.raises(ValueError):
        timeframe_seconds("0m")


def test_tick_aggregator_builds_ohlcv_and_finalizes_on_bucket_change():
    aggregator = TickCandleAggregator()
    base = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    assert aggregator.ingest(MarketTick("NIFTY", base + timedelta(seconds=5), 100, 10), "5m") == []
    assert aggregator.ingest(MarketTick("NIFTY", base + timedelta(seconds=20), 103, 20), "5m") == []
    assert aggregator.current("NIFTY", "5m").high == 103
    assert aggregator.current("NIFTY", "5m").low == 100
    assert aggregator.current("NIFTY", "5m").volume == 30

    finalized = aggregator.ingest(MarketTick("NIFTY", base + timedelta(minutes=5, seconds=1), 101, 5), "5m")
    assert len(finalized) == 1
    assert finalized[0].timestamp == base
    assert finalized[0].open == 100
    assert finalized[0].high == 103
    assert finalized[0].low == 100
    assert finalized[0].close == 103
    assert finalized[0].volume == 30
    assert aggregator.current("NIFTY", "5m").open == 101


def test_tick_aggregator_does_not_create_synthetic_gap_candles():
    aggregator = TickCandleAggregator()
    base = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    aggregator.ingest(MarketTick("NIFTY", base + timedelta(seconds=1), 100, 1), "5m")
    finalized = aggregator.ingest(MarketTick("NIFTY", base + timedelta(minutes=15, seconds=1), 110, 2), "5m")
    assert len(finalized) == 1
    assert finalized[0].timestamp == base
    assert aggregator.current("NIFTY", "5m").timestamp == base + timedelta(minutes=15)


def test_tick_aggregator_rejects_duplicate_or_out_of_order_ticks_without_mutation():
    aggregator = TickCandleAggregator()
    base = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    assert aggregator.ingest(MarketTick("NIFTY", base, 100, 10), "5m") == []
    assert aggregator.ingest(MarketTick("NIFTY", base, 200, 20), "5m") == []
    assert aggregator.ingest(MarketTick("NIFTY", base - timedelta(seconds=1), 50, 5), "5m") == []
    current = aggregator.current("NIFTY", "5m")
    assert current.open == 100 and current.close == 100 and current.volume == 10


def test_tick_aggregator_flushes_selected_active_buckets():
    aggregator = TickCandleAggregator()
    base = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    aggregator.ingest(MarketTick("NIFTY", base, 100, 1), "5m")
    aggregator.ingest(MarketTick("BANKNIFTY", base, 200, 2), "5m")
    flushed = aggregator.flush("NIFTY", "5m")
    assert len(flushed) == 1
    assert flushed[0].symbol == "NIFTY"
    assert aggregator.current("NIFTY", "5m") is None
    assert aggregator.current("BANKNIFTY", "5m") is not None
