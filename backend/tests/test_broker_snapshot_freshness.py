from datetime import datetime, timedelta, timezone

from app.broker_portfolio_snapshot import BrokerPortfolioSnapshot
from app.broker_snapshot_freshness import BrokerSnapshotFreshnessPolicy


def test_fresh_snapshot_is_accepted():
    now = datetime.now(timezone.utc)
    snapshot = BrokerPortfolioSnapshot.from_data("paper", [], [], now - timedelta(seconds=2))
    result = BrokerSnapshotFreshnessPolicy(max_age_seconds=5).evaluate(snapshot, now)
    assert result.fresh is True
    assert result.age_seconds == 2


def test_stale_snapshot_is_rejected():
    now = datetime.now(timezone.utc)
    snapshot = BrokerPortfolioSnapshot.from_data("paper", [], [], now - timedelta(seconds=6))
    result = BrokerSnapshotFreshnessPolicy(max_age_seconds=5).evaluate(snapshot, now)
    assert result.fresh is False
    assert "stale" in result.reason


def test_future_snapshot_is_rejected():
    now = datetime.now(timezone.utc)
    snapshot = BrokerPortfolioSnapshot.from_data("paper", [], [], now + timedelta(seconds=1))
    result = BrokerSnapshotFreshnessPolicy().evaluate(snapshot, now)
    assert result.fresh is False
    assert "future" in result.reason
