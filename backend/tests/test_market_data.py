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
