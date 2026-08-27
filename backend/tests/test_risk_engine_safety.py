import math

import pytest

from app.risk_engine import RiskLimits, evaluate


def base_kwargs():
    return dict(
        equity=100_000,
        daily_pnl=0,
        proposed_risk=500,
        proposed_exposure=10_000,
        open_positions=0,
    )


@pytest.mark.parametrize(
    "field",
    ["equity", "daily_pnl", "proposed_risk", "proposed_exposure", "current_exposure", "unrealized_pnl"],
)
def test_non_finite_numeric_inputs_fail_closed(field):
    kwargs = base_kwargs()
    kwargs[field] = math.nan
    with pytest.raises(ValueError, match="numeric and finite"):
        evaluate(**kwargs)


@pytest.mark.parametrize(
    "field",
    ["equity", "daily_pnl", "proposed_risk", "proposed_exposure", "current_exposure", "unrealized_pnl"],
)
def test_infinite_numeric_inputs_fail_closed(field):
    kwargs = base_kwargs()
    kwargs[field] = math.inf
    with pytest.raises(ValueError, match="numeric and finite"):
        evaluate(**kwargs)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("proposed_risk", -1, "invalid proposed risk"),
        ("proposed_exposure", -1, "invalid proposed exposure"),
        ("current_exposure", -1, "invalid current exposure"),
        ("open_positions", -1, "invalid open positions"),
        ("recent_losses", -1, "invalid recent losses"),
    ],
)
def test_negative_portfolio_inputs_fail_closed(field, value, reason):
    kwargs = base_kwargs()
    kwargs[field] = value
    decision = evaluate(**kwargs)
    assert not decision.allowed
    assert reason in decision.reasons


@pytest.mark.parametrize(
    "limits",
    [
        RiskLimits(max_risk_percent=math.nan),
        RiskLimits(max_daily_loss_percent=math.inf),
        RiskLimits(max_exposure_percent=-1),
        RiskLimits(max_positions=-1),
        RiskLimits(cooldown_after_loss=-1),
    ],
)
def test_invalid_limits_fail_closed(limits):
    with pytest.raises(ValueError):
        evaluate(**base_kwargs(), limits=limits)


def test_valid_risk_inputs_remain_allowed():
    decision = evaluate(**base_kwargs())
    assert decision.allowed
    assert decision.reasons == []
    assert decision.risk_amount == 500
    assert decision.exposure == 10_000
