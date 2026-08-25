from datetime import datetime, timezone

import pytest

from app.broker_portfolio_snapshot import (
    BrokerOpenOrder,
    BrokerPortfolioSnapshot,
    BrokerPosition,
)


def test_snapshot_normalizes_broker_and_freezes_collections():
    snapshot = BrokerPortfolioSnapshot.from_data(
        " Dhan ",
        [BrokerPosition("NIFTY", 10, 1000, 950)],
        [BrokerOpenOrder("o1", "BANKNIFTY", 5, 2000, 1900)],
        datetime.now(timezone.utc),
    )
    assert snapshot.broker == "dhan"
    assert len(snapshot.positions) == 1
    assert len(snapshot.open_orders) == 1
    assert snapshot.data_complete is True


def test_snapshot_requires_broker_name():
    with pytest.raises(ValueError):
        BrokerPortfolioSnapshot.from_data("  ", [], [], datetime.now(timezone.utc))


def test_incomplete_snapshot_can_be_explicitly_marked():
    snapshot = BrokerPortfolioSnapshot.from_data(
        "paper", [], [], datetime.now(timezone.utc), data_complete=False, error="positions unavailable"
    )
    assert snapshot.data_complete is False
    assert snapshot.error == "positions unavailable"
