from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.market_data import Candle
from app.market_data_store import MarketDataStore


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def candle(ts, close=101.0):
    return Candle(ts, 100.0, 102.0, 99.0, close, 1000.0, " nifty ", "5m")


def test_upsert_is_idempotent(db):
    store = MarketDataStore(db)
    ts = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
    store.upsert(candle(ts))
    store.upsert(candle(ts, 103.0))
    db.commit()
    rows = store.candles("NIFTY", "5m")
    assert len(rows) == 1
    assert rows[0].close == 103.0


def test_reads_are_oldest_first_and_limited(db):
    store = MarketDataStore(db)
    base = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
    for i in range(3):
        store.upsert(candle(base + timedelta(minutes=5 * i), 101 + i))
    db.commit()
    rows = store.candles("NIFTY", "5m", limit=2)
    assert [r.close for r in rows] == [102.0, 103.0]


def test_invalid_ohlc_is_rejected(db):
    store = MarketDataStore(db)
    bad = Candle(datetime.now(timezone.utc), 100, 99, 98, 98.5, 1, "NIFTY", "5m")
    with pytest.raises(ValueError, match="invalid candle OHLC"):
        store.upsert(bad)
