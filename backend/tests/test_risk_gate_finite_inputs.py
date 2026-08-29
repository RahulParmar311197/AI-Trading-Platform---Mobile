import math

import pytest

from app.broker_adapter import BrokerOrderRequest
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot


def _gate() -> PreTradeRiskGate:
    return PreTradeRiskGate(RiskLimits(
        max_order_quantity=100,
        max_position_quantity=200,
        max_daily_loss=10_000,
        max_trade_loss=1_000,
    ))


def _request(quantity: float = 1.0) -> BrokerOrderRequest:
    return BrokerOrderRequest(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=quantity,
        broker_account_id=1,
        broker_route="TEST",
    )


@pytest.mark.parametrize("quantity", [math.nan, math.inf, -math.inf])
def test_non_finite_order_quantity_is_rejected(quantity):
    decision = _gate().evaluate(_request(quantity), RiskSnapshot(broker_ready=True))
    assert decision.allowed is False
    assert decision.reason == "RISK_INVALID_NUMERIC_INPUT"


@pytest.mark.parametrize("position", [math.nan, math.inf, -math.inf])
def test_non_finite_position_is_rejected(position):
    decision = _gate().evaluate(_request(), RiskSnapshot(position_quantity=position, broker_ready=True))
    assert decision.allowed is False
    assert decision.reason == "RISK_INVALID_NUMERIC_INPUT"


@pytest.mark.parametrize("daily_pnl", [math.nan, math.inf, -math.inf])
def test_non_finite_daily_pnl_is_rejected(daily_pnl):
    decision = _gate().evaluate(_request(), RiskSnapshot(daily_pnl=daily_pnl, broker_ready=True))
    assert decision.allowed is False
    assert decision.reason == "RISK_INVALID_NUMERIC_INPUT"


@pytest.mark.parametrize("trade_loss", [math.nan, math.inf, -math.inf])
def test_non_finite_projected_trade_loss_is_rejected(trade_loss):
    decision = _gate().evaluate(_request(), RiskSnapshot(projected_trade_loss=trade_loss, broker_ready=True))
    assert decision.allowed is False
    assert decision.reason == "RISK_INVALID_NUMERIC_INPUT"


@pytest.mark.parametrize("field,value", [
    ("max_order_quantity", math.nan),
    ("max_order_quantity", math.inf),
    ("max_position_quantity", math.nan),
    ("max_daily_loss", math.inf),
    ("max_trade_loss", math.nan),
])
def test_non_finite_limits_are_rejected(field, value):
    values = dict(max_order_quantity=100, max_position_quantity=200, max_daily_loss=10_000, max_trade_loss=1_000)
    values[field] = value
    with pytest.raises(ValueError, match="risk limits must be finite"):
        PreTradeRiskGate(RiskLimits(**values))


def test_finite_request_remains_allowed():
    decision = _gate().evaluate(_request(5), RiskSnapshot(broker_ready=True))
    assert decision == type(decision)(True, "RISK_OK")
