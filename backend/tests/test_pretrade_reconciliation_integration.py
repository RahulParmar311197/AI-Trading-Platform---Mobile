from app.ai_decision_engine import TradingDecision
from app.broker_portfolio_provider import PaperBrokerPortfolioProvider
from app.broker_portfolio_snapshot import BrokerPortfolioSnapshot
from app.broker_portfolio_snapshot import BrokerOpenOrder, BrokerPosition
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_blocks_position_reconciliation_drift():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(positions=(BrokerPosition("NIFTY", 10, 1000, 950),))
    result = PreTradeOrchestrator(broker_provider=provider).authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", .95, "reconciliation"),
        equity=1_000_000, daily_pnl=0, open_positions=1, exposure_price=1000,
        internal_positions={"NIFTY": 5}, internal_open_order_ids=set(),
    )
    assert result.approved is False
    assert "reconciliation drift" in result.reason


def test_pretrade_allows_clean_reconciliation():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(
        positions=(BrokerPosition("NIFTY", 10, 1000, 950),),
        open_orders=(BrokerOpenOrder("o1", "NIFTY", 1, 1000, 950),),
    )
    result = PreTradeOrchestrator(broker_provider=provider).authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", .95, "reconciliation"),
        equity=1_000_000, daily_pnl=0, open_positions=1, exposure_price=1000,
        internal_positions={"NIFTY": 10}, internal_open_order_ids={"o1"},
    )
    assert result.approved is True
