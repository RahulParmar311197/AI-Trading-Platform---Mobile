from app.broker_portfolio_provider import PaperBrokerPortfolioProvider
from app.broker_portfolio_snapshot import BrokerOpenOrder, BrokerPosition


def test_paper_provider_returns_fresh_canonical_snapshot():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(
        positions=(BrokerPosition("NIFTY", 10, 1000, 950),),
        open_orders=(BrokerOpenOrder("o1", "BANKNIFTY", 5, 2000, 1900),),
    )
    snapshot = provider.get_portfolio_snapshot()
    assert snapshot.broker == "paper"
    assert snapshot.data_complete is True
    assert snapshot.positions[0].symbol == "NIFTY"
    assert snapshot.open_orders[0].order_id == "o1"


def test_paper_provider_can_fail_closed():
    provider = PaperBrokerPortfolioProvider()
    provider.set_snapshot(data_complete=False, error="portfolio unavailable")
    snapshot = provider.get_portfolio_snapshot()
    assert snapshot.data_complete is False
    assert snapshot.error == "portfolio unavailable"
