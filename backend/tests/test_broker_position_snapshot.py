import pytest

from app.broker_position_snapshot import BrokerPositionSnapshot


def test_authoritative_position_snapshot_can_be_consumed():
    snapshot = BrokerPositionSnapshot(positions=[{"symbol": "NIFTY", "quantity": 10}], complete=True)
    assert snapshot.require_authoritative() == [{"symbol": "NIFTY", "quantity": 10}]


def test_incomplete_position_snapshot_fails_closed():
    snapshot = BrokerPositionSnapshot(positions=[], complete=False)
    with pytest.raises(RuntimeError, match="not authoritative"):
        snapshot.require_authoritative()
