from datetime import datetime, timezone

import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_trade_intent import AITradeIntentConfig, build_ai_order_request
from app.instruments import InstrumentProvider, InstrumentSpec


class StaticProvider(InstrumentProvider):
    def __init__(self, instrument):
        self.instrument = instrument

    def resolve(self, symbol):
        return self.instrument if symbol == self.instrument.symbol else None


def decision(side="BUY", symbol="NIFTY"):
    return TradingDecision(
        symbol=symbol,
        decision=side,
        confidence=0.9,
        entry=100.0,
        stop_loss=90.0 if side == "BUY" else 110.0,
        target=120.0 if side == "BUY" else 80.0,
        reasons=("test",),
    )


def provider():
    return StaticProvider(InstrumentSpec(symbol="NIFTY", security_id="NIFTY-TEST", exchange_segment="NSE_FO", lot_size=50, tick_size=0.05, multiplier=1.0, tradable=True))


def test_builds_sized_buy_request():
    request = build_ai_order_request(decision(), equity=100_000, client_order_id="ai-1", instrument_provider=provider())
    assert request is not None
    assert request.side == "BUY"
    assert request.symbol == "NIFTY"
    assert request.quantity == 100
    assert request.security_id == "NIFTY-TEST"
    assert request.stop == 90.0
    assert request.target == 120.0


def test_builds_request_with_opaque_broker_account_identity():
    request = build_ai_order_request(
        decision(), equity=100_000, client_order_id="ai-account",
        instrument_provider=provider(), broker_account_id="001",
    )
    assert request is not None
    assert request.broker_account_id == "001"


def test_distinct_broker_account_identities_do_not_numeric_alias():
    first = build_ai_order_request(
        decision(), equity=100_000, client_order_id="ai-account-1",
        instrument_provider=provider(), broker_account_id="001",
    )
    second = build_ai_order_request(
        decision(), equity=100_000, client_order_id="ai-account-2",
        instrument_provider=provider(), broker_account_id="1",
    )
    assert first.broker_account_id == "001"
    assert second.broker_account_id == "1"
    assert first.broker_account_id != second.broker_account_id


def test_rejects_blank_broker_account_identity():
    with pytest.raises(ValueError, match="broker_account_id must be a non-empty string"):
        build_ai_order_request(
            decision(), equity=100_000, client_order_id="ai-account-empty",
            instrument_provider=provider(), broker_account_id="   ",
        )


def test_hold_is_not_executable():
    hold = TradingDecision(symbol="NIFTY", decision="HOLD", confidence=0.9, entry=None, stop_loss=None, target=None, reasons=("hold",))
    assert build_ai_order_request(hold, equity=100_000, client_order_id="ai-2", instrument_provider=provider()) is None


def test_sell_geometry_is_validated():
    request = build_ai_order_request(decision("SELL"), equity=100_000, client_order_id="ai-3", instrument_provider=provider())
    assert request.side == "SELL"


def test_rejects_missing_symbol_metadata():
    with pytest.raises(ValueError, match="metadata unavailable"):
        build_ai_order_request(decision(symbol="UNKNOWN"), equity=100_000, client_order_id="ai-4", instrument_provider=provider())
