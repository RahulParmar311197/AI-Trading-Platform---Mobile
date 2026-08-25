from datetime import datetime, timezone

from app.ai_decision_engine import TradingDecision
from app.broker_portfolio_snapshot import BrokerOpenOrder, BrokerPortfolioSnapshot, BrokerPosition
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
from app.pretrade_orchestrator import PreTradeOrchestrator


def make_snapshot():
    return BrokerPortfolioSnapshot.from_data(
        "paper",
        [BrokerPosition("NIFTY", 10, 1000, 950)],
        [BrokerOpenOrder("o1", "BANKNIFTY", 5, 2000, 1900)],
        datetime.now(timezone.utc),
    )


def test_broker_snapshot_drives_live_risk_aggregation():
    orchestrator = PreTradeOrchestrator(
        portfolio_loss_risk=PortfolioLossRisk(PortfolioRiskLimits(max_risk_budget=1200))
    )
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", 0.95, "snapshot"),
        equity=1_000_000, daily_pnl=0, open_positions=1,
        exposure_price=1000, broker_snapshot=make_snapshot(),
    )
    assert result.approved is False
    assert "risk budget" in result.reason


def test_incomplete_broker_snapshot_fails_closed_before_order():
    snapshot = BrokerPortfolioSnapshot.from_data(
        "paper", [], [], datetime.now(timezone.utc), data_complete=False, error="broker unavailable"
    )
    orchestrator = PreTradeOrchestrator()
    result = orchestrator.authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", 0.95, "snapshot"),
        equity=1_000_000, daily_pnl=0, open_positions=0,
        exposure_price=1000, broker_snapshot=snapshot,
    )
    assert result.approved is False
    assert "unavailable" in result.reason
