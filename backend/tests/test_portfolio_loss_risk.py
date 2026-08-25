import pytest

from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits


def test_allows_trade_inside_portfolio_risk_budget():
    result = PortfolioLossRisk(PortfolioRiskLimits(max_daily_loss=5000, max_drawdown=10000, max_risk_budget=3000)).evaluate(
        daily_pnl=-1000, current_drawdown=2000, open_risk=500, proposed_risk=1000
    )
    assert result.approved is True
    assert result.projected_risk == 1500


@pytest.mark.parametrize("limits, kwargs, reason", [
    (PortfolioRiskLimits(max_daily_loss=5000), dict(daily_pnl=-4500, current_drawdown=0, open_risk=0, proposed_risk=1000), "daily loss"),
    (PortfolioRiskLimits(max_drawdown=5000), dict(daily_pnl=0, current_drawdown=4500, open_risk=0, proposed_risk=1000), "drawdown"),
    (PortfolioRiskLimits(max_risk_budget=1500), dict(daily_pnl=0, current_drawdown=0, open_risk=1000, proposed_risk=600), "risk budget"),
])
def test_blocks_projected_portfolio_risk(limit, kwargs, reason):
    result = PortfolioLossRisk(limit).evaluate(**kwargs)
    assert result.approved is False
    assert reason in result.reason


def test_missing_portfolio_data_fails_closed():
    result = PortfolioLossRisk(PortfolioRiskLimits(max_risk_budget=10000)).evaluate(
        daily_pnl=0, current_drawdown=0, open_risk=0, proposed_risk=1, positions_available=False
    )
    assert result.approved is False
