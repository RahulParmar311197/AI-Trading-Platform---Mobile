from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.instrument_service import InstrumentService, InstrumentValidationError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_upsert_normalizes_symbol_and_reads_it(db):
    service = InstrumentService(db)
    instrument = service.upsert(symbol=" nifty ", exchange="NSE", asset_class="index")
    db.commit()
    assert instrument.symbol == "NIFTY"
    assert service.get("nifty").symbol == "NIFTY"


def test_option_requires_contract_fields(db):
    with pytest.raises(InstrumentValidationError):
        InstrumentService(db).upsert(
            symbol="NIFTY-OPTION", exchange="NSE", asset_class="index", instrument_type="OPTION"
        )


def test_option_is_valid_with_contract_fields(db):
    service = InstrumentService(db)
    instrument = service.upsert(
        symbol="NIFTY26AUG25000CE",
        exchange="NSE",
        asset_class="index",
        instrument_type="OPTION",
        underlying_symbol="NIFTY",
        expiry_date=datetime(2026, 8, 27, tzinfo=timezone.utc),
        strike_price=Decimal("25000"),
        option_type="CE",
    )
    assert instrument.option_type == "CE"
    assert instrument.strike_price == Decimal("25000")


def test_list_can_filter_by_exchange(db):
    service = InstrumentService(db)
    service.upsert(symbol="NIFTY", exchange="NSE", asset_class="index")
    service.upsert(symbol="RELIANCE", exchange="NSE", asset_class="equity")
    service.upsert(symbol="USDINR", exchange="CURRENCY", asset_class="currency")
    db.commit()
    assert [x.symbol for x in service.list(exchange="NSE")] == ["NIFTY", "RELIANCE"]
