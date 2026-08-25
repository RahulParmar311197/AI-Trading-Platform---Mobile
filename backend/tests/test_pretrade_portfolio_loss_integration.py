from app.ai_decision_engine import TradingDecision
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_blocks_projected_daily_loss():
    orchestrator = PreTradeOrchestrator(
        portfolio_loss_risk=PortfolioLossRisk(PortfolioRiskLimits(max_daily_loss=5000))
    )
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="portfolio loss test")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=100000, daily_pnl=-4500,
        open_positions=1, positions={"NIFTY": 1}, exposure_price=1000,
    )
    assert result.approved is False
    assert result.gateway is None
    assert "daily loss" in result.reason


def test_pretrade_blocks_projected_risk_budget():
    orchestrator = PreTradeOrchestrator(
        portfolio_loss_risk=PortfolioLossRisk(PortfolioRiskLimits(max_risk_budget=1000))
    )
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="risk budget test")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=100000, daily_pnl=0,
        open_positions=1, positions={"NIFTY": 1}, exposure_price=1000,
        open_risk=900,
    )
    assert result.approved is False
    assert result.gateway is None
    assert "risk budget" in result.reason
