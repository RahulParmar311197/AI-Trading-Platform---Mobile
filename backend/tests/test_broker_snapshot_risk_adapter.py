from datetime import datetime, timedelta, timezone

from app.broker_portfolio_snapshot import BrokerOpenOrder, BrokerPortfolioSnapshot, BrokerPosition
from app.broker_snapshot_risk_adapter import BrokerSnapshotRiskAdapter


def snapshot(**kwargs):
    return BrokerPortfolioSnapshot.from_data(
        "paper",
        kwargs.pop("positions", []),
        kwargs.pop("open_orders", []),
        kwargs.pop("captured_at", datetime.now(timezone.utc)),
        **kwargs,
    )


def test_adapts_complete_snapshot():
    result = BrokerSnapshotRiskAdapter().adapt(snapshot(
        positions=[BrokerPosition("NIFTY", 10, 1000, 950)],
        open_orders=[BrokerOpenOrder("o1", "BANKNIFTY", 5, 2000, 1900)],
    ))
    assert result.available is True
    assert result.positions[0].symbol == "NIFTY"
    assert result.open_orders[0].symbol == "BANKNIFTY"


def test_incomplete_snapshot_blocks_risk_use():
    result = BrokerSnapshotRiskAdapter().adapt(snapshot(data_complete=False, error="broker unavailable"))
    assert result.available is False
    assert "unavailable" in result.reason


def test_future_snapshot_is_rejected():
    result = BrokerSnapshotRiskAdapter().adapt(snapshot(captured_at=datetime.now(timezone.utc) + timedelta(minutes=1)))
    assert result.available is False
    assert "future" in result.reason


def test_naive_timestamp_is_rejected():
    result = BrokerSnapshotRiskAdapter().adapt(snapshot(captured_at=datetime.now()))
    assert result.available is False
    assert "timezone" in result.reason
