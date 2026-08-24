from app.db import Base
from app.models import Instrument, MarketCandle, Order, Position, User


def test_all_sql_models_share_one_canonical_metadata():
    models = (User, Order, Instrument, MarketCandle, Position)

    assert {model.metadata for model in models} == {Base.metadata}
    assert {
        model.__table__.metadata for model in models
    } == {Base.metadata}


def test_canonical_models_register_expected_tables_once():
    expected = {"users", "orders", "instruments", "market_candles", "positions"}

    assert expected.issubset(Base.metadata.tables)
    assert {User.__tablename__, Order.__tablename__, Instrument.__tablename__, MarketCandle.__tablename__, Position.__tablename__} == expected
