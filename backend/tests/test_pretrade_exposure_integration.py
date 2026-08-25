from app.ai_decision_engine import TradingDecision
from app.portfolio_exposure_risk import ExposureLimits, PortfolioExposureRisk
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_blocks_exposure_breach():
    orchestrator = PreTradeOrchestrator(
        exposure_risk=PortfolioExposureRisk(
            ExposureLimits(max_symbol_quantity=25, max_symbol_notional=50000, max_total_notional=100000)
        )
    )
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="exposure test")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=100000, daily_pnl=0,
        open_positions=1, positions={"NIFTY": 20}, exposure_price=1000,
    )
    assert result.approved is False
    assert result.gateway is None
    assert "max symbol quantity" in result.reason


def test_pretrade_allows_exposure_within_limits():
    orchestrator = PreTradeOrchestrator(
        exposure_risk=PortfolioExposureRisk(
            ExposureLimits(max_symbol_quantity=100, max_symbol_notional=200000, max_total_notional=500000)
        )
    )
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="exposure test")
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=decision, equity=1000000, daily_pnl=0,
        open_positions=1, positions={"NIFTY": 5}, exposure_price=1000,
    )
    assert result.approved is True
