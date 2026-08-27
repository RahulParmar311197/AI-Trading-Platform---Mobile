import pytest

from app.instruments import InstrumentSpec, StaticInstrumentProvider


def test_resolve_is_case_insensitive_and_unknown_fails_closed():
    provider = StaticInstrumentProvider([
        InstrumentSpec(
            symbol="NIFTY",
            security_id="NSE_INDEX|Nifty 50",
            exchange_segment="NSE_INDEX",
            lot_size=1,
            tick_size=0.05,
        )
    ])

    assert provider.resolve("nifty").security_id == "NSE_INDEX|Nifty 50"
    assert provider.resolve("UNKNOWN") is None


def test_instrument_spec_rejects_invalid_trading_metadata():
    with pytest.raises(ValueError, match="lot_size"):
        InstrumentSpec(
            symbol="NIFTY",
            security_id="id",
            exchange_segment="NSE_INDEX",
            lot_size=0,
        )
