from decimal import Decimal

from app.models import Instrument


def test_spot_instrument_defaults():
    instrument = Instrument(symbol="NIFTY", exchange="NSE", asset_class="index")
    assert instrument.instrument_type == "SPOT"
    assert instrument.underlying_symbol is None
    assert instrument.expiry_date is None
    assert instrument.strike_price is None
    assert instrument.option_type is None


def test_option_instrument_fields():
    instrument = Instrument(
        symbol="NIFTY26AUG25000CE",
        exchange="NSE",
        asset_class="index",
        instrument_type="OPTION",
        underlying_symbol="NIFTY",
        strike_price=Decimal("25000"),
        option_type="CE",
        tick_size=Decimal("0.05"),
        lot_size=Decimal("75"),
    )
    assert instrument.instrument_type == "OPTION"
    assert instrument.underlying_symbol == "NIFTY"
    assert instrument.strike_price == Decimal("25000")
    assert instrument.option_type == "CE"
    assert instrument.tick_size == Decimal("0.05")
    assert instrument.lot_size == Decimal("75")
