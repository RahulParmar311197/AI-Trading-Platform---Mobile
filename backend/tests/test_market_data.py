from datetime import datetime, timedelta, timezone
import pytest
from app.market_data import Candle, MarketTick, InMemoryMarketData


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
