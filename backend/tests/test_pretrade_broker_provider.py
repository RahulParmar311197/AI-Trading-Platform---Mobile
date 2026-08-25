from app.ai_decision_engine import TradingDecision
from app.broker_portfolio_provider import PaperBrokerPortfolioProvider
from app.broker_portfolio_snapshot import BrokerPosition
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_fetches_provider_snapshot_automatically():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(positions=(BrokerPosition("NIFTY", 10, 1000, 950),))
    orchestrator = PreTradeOrchestrator(
        broker_provider=provider,
        portfolio_loss_risk=PortfolioLossRisk(PortfolioRiskLimits(max_risk_budget=600)),
    )
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", 0.95, "provider"),
        equity=1_000_000, daily_pnl=0, open_positions=1, exposure_price=1000,
    )
    assert result.approved is False
    assert "risk budget" in result.reason


def test_pretrade_fails_closed_when_provider_snapshot_is_incomplete():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(data_complete=False, error="paper state unavailable")
    orchestrator = PreTradeOrchestrator(broker_provider=provider)
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", 0.95, "provider"),
        equity=1_000_000, daily_pnl=0, open_positions=0, exposure_price=1000,
    )
    assert result.approved is False
    assert "unavailable" in result.reason
