import pytest

from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits


def make_order(risk=50.0, quantity=1.0):
    return OrderIntent("NIFTY", "BUY", 100.0, 90.0, 120.0, quantity, risk, "strategy", 0.9)


def test_exact_risk_limit_is_allowed():
    result = authorize(
        order=make_order(100.0), equity=10000, daily_pnl=0, open_positions=0,
        limits=RiskLimits(max_risk_percent=1.0),
    )
    assert result.approved


def test_exact_daily_loss_limit_is_blocked():
    result = authorize(
        order=make_order(), equity=10000, daily_pnl=-300, open_positions=0,
        limits=RiskLimits(max_daily_loss_percent=3.0),
    )
    assert not result.approved
    assert "daily loss limit reached" in result.decision.reasons


def test_exact_exposure_limit_is_allowed():
    result = authorize(
        order=make_order(quantity=20), equity=10000, daily_pnl=0, open_positions=0,
        limits=RiskLimits(max_exposure_percent=20.0),
    )
    assert result.approved


def test_position_limit_blocks_new_trade():
    result = authorize(
        order=make_order(), equity=10000, daily_pnl=0, open_positions=5,
        limits=RiskLimits(max_positions=5),
    )
    assert not result.approved
    assert "maximum open positions reached" in result.decision.reasons


def test_loss_cooldown_blocks_until_losses_recover():
    limits = RiskLimits(cooldown_after_loss=3)
    blocked = authorize(order=make_order(), equity=10000, daily_pnl=0, open_positions=0, recent_losses=2, limits=limits)
    allowed = authorize(order=make_order(), equity=10000, daily_pnl=0, open_positions=0, recent_losses=3, limits=limits)
    assert not blocked.approved
    assert allowed.approved


def test_non_positive_equity_is_rejected():
    result = authorize(order=make_order(), equity=0, daily_pnl=0, open_positions=0)
    assert not result.approved
    assert "invalid equity" in result.decision.reasons
