from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.historical_replay import HistoricalReplay, ReplayConfig
from app.market_data import Candle
from app.market_data_store import MarketDataStore


def test_replay_is_ordered_and_batched():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        store = MarketDataStore(db)
        base = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
        for i in range(5):
            ts = base + timedelta(minutes=5 * i)
            store.upsert(Candle(ts, 100, 102, 99, 101 + i, 1000, "NIFTY", "5m"))
        db.commit()

        rows = HistoricalReplay(store).collect(ReplayConfig("NIFTY", "5m", batch_size=2))
        assert [r.close for r in rows] == [101, 102, 103, 104, 105]


def test_replay_respects_time_window():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        store = MarketDataStore(db)
        base = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
        for i in range(5):
            ts = base + timedelta(minutes=5 * i)
            store.upsert(Candle(ts, 100, 102, 99, 101 + i, 1000, "NIFTY", "5m"))
        db.commit()

        rows = HistoricalReplay(store).collect(
            ReplayConfig("NIFTY", "5m", start=base + timedelta(minutes=5), end=base + timedelta(minutes=15), batch_size=2)
        )
        assert [r.close for r in rows] == [102, 103, 104]
