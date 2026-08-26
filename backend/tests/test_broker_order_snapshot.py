import pytest

from app.broker_order_snapshot import BrokerOrderSnapshot


def test_authoritative_snapshot_can_be_consumed():
    snapshot = BrokerOrderSnapshot(orders=[{"order_id": "1"}], complete=True)
    assert snapshot.require_authoritative() == [{"order_id": "1"}]


def test_incomplete_snapshot_fails_closed():
    snapshot = BrokerOrderSnapshot(orders=[], complete=False)
    with pytest.raises(RuntimeError, match="not authoritative"):
        snapshot.require_authoritative()


def test_snapshot_source_is_retained():
    snapshot = BrokerOrderSnapshot(orders=[], complete=True, source="upstox")
    assert snapshot.source == "upstox"
