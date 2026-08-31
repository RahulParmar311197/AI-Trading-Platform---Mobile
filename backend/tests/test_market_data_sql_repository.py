from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.market_data.models import Candle, Instrument, Timeframe
from app.market_data.repository import SqlAlchemyHistoricalCandleRepository
from app.models.market_candle import MarketCandle


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return SqlAlchemyHistoricalCandleRepository(factory)


def candle(close=101.0):
    return Candle(
        instrument=Instrument(symbol="RELIANCE", exchange="NSE"),
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
        open=100.0, high=102.0, low=99.0, close=close, volume=50.0,
    )


def test_upsert_and_get_are_durable(repository):
    assert repository.upsert([candle()]) == 1
    result = repository.get(candle().instrument, candle().timeframe, candle().timestamp, candle().timestamp)
    assert len(result) == 1
    assert result[0].close == 101.0
    assert repository.count() == 1


def test_upsert_replaces_same_canonical_candle(repository):
    repository.upsert([candle(101.0)])
    repository.upsert([candle(103.0)])
    result = repository.get(candle().instrument, candle().timeframe, candle().timestamp, candle().timestamp)
    assert len(result) == 1
    assert result[0].close == 103.0
    assert repository.count() == 1
