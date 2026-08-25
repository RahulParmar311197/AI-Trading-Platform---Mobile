from app.ai_decision_engine import TradingDecision
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
from app.portfolio_risk_aggregation import OpenOrderRiskInput, PositionRiskInput
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_uses_aggregated_open_risk():
    orchestrator = PreTradeOrchestrator(
        portfolio_loss_risk=PortfolioLossRisk(PortfolioRiskLimits(max_risk_budget=1200))
    )
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="aggregation test")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=1000000, daily_pnl=0,
        open_positions=1, positions={"NIFTY": 1}, exposure_price=1000,
        position_risk_inputs=[PositionRiskInput("NIFTY", 10, 1000, 950)],
        open_order_risk_inputs=[OpenOrderRiskInput("BANKNIFTY", 5, 2000, 1900)],
    )
    assert result.approved is False
    assert "risk budget" in result.reason


def test_pretrade_blocks_when_live_risk_data_unresolved():
    orchestrator = PreTradeOrchestrator()
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="fail closed")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=1000000, daily_pnl=0,
        open_positions=1, positions={"NIFTY": 1}, exposure_price=1000,
        position_risk_inputs=[PositionRiskInput("NIFTY", 10, 1000, None)],
        open_order_risk_inputs=[],
    )
    assert result.approved is False
    assert "unavailable" in result.reason
