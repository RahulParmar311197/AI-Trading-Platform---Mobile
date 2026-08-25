from app.ai_decision_engine import TradingDecision
from app.broker_portfolio_provider import PaperBrokerPortfolioProvider
from app.broker_portfolio_snapshot import BrokerPosition
from app.internal_trading_state_provider import InMemoryTradingStateProvider
from app.pretrade_orchestrator import PreTradeOrchestrator


def test_pretrade_fetches_internal_state_automatically():
    broker = PaperBrokerPortfolioProvider()
    broker.set_snapshot(positions=(BrokerPosition("NIFTY", 10, 1000, 950),))
    internal = InMemoryTradingStateProvider()
    internal.set_state(positions={"NIFTY": 5}, open_order_ids=set())
    result = PreTradeOrchestrator(broker_provider=broker, internal_state_provider=internal).authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", .95, "auto state"),
        equity=1_000_000, daily_pnl=0, open_positions=1, exposure_price=1000,
    )
    assert result.approved is False
    assert "reconciliation drift" in result.reason


def test_pretrade_clean_internal_state_continues():
    broker = PaperBrokerPortfolioProvider()
    broker.set_snapshot(positions=(BrokerPosition("NIFTY", 10, 1000, 950),))
    internal = InMemoryTradingStateProvider()
    internal.set_state(positions={"NIFTY": 10}, open_order_ids=set())
    result = PreTradeOrchestrator(broker_provider=broker, internal_state_provider=internal).authorize_decision(
        symbol="NIFTY", decision=TradingDecision("BUY", .95, "auto state"),
        equity=1_000_000, daily_pnl=0, open_positions=1, exposure_price=1000,
    )
    assert result.approved is True
