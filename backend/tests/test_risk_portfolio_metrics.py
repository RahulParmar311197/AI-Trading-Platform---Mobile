from app.risk_engine import RiskLimits, evaluate


def test_post_trade_exposure_is_checked_as_absolute_value():
    decision = evaluate(
        equity=100000,
        daily_pnl=0,
        proposed_risk=500,
        proposed_exposure=-25000,
        open_positions=1,
    )
    assert decision.allowed

    blocked = evaluate(
        equity=100000,
        daily_pnl=0,
        proposed_risk=500,
        proposed_exposure=-25001,
        open_positions=1,
        limits=RiskLimits(max_exposure_percent=25),
    )
    assert not blocked.allowed
    assert "portfolio exposure exceeds limit" in blocked.reasons


def test_daily_loss_limit_uses_authoritative_daily_pnl():
    decision = evaluate(
        equity=100000,
        daily_pnl=-3000,
        proposed_risk=100,
        proposed_exposure=1000,
        open_positions=0,
    )
    assert not decision.allowed
    assert "daily loss limit reached" in decision.reasons


def test_unrealized_pnl_is_explicit_portfolio_input_without_replacing_daily_pnl():
    decision = evaluate(
        equity=100000,
        daily_pnl=-1000,
        proposed_risk=100,
        proposed_exposure=1000,
        open_positions=0,
        unrealized_pnl=-5000,
        current_exposure=15000,
    )
    assert decision.allowed
